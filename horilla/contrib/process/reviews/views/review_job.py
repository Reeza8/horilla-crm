"""Views for Review Process job view ."""

# Third-party imports (Django)
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView

from horilla.contrib.generics.views import HorillaListView, HorillaNavView, HorillaView

# First party imports (Horilla)
from horilla.contrib.notifications.methods import create_notification
from horilla.db import models as db_models
from horilla.db.models import Q
from horilla.shortcuts import get_object_or_404, render
from horilla.urls import reverse, reverse_lazy

# First party imports (Horilla)
from horilla.utils import timezone
from horilla.utils.decorators import htmx_required, method_decorator
from horilla.utils.translation import gettext_lazy as _
from horilla.web import Http404, HttpResponse, ScriptResponse

# Local imports
from ..filters import ReviewJobFilter
from ..models import ReviewJob
from ..views.helper import (
    _aggregate_field_comment,
    _aggregate_field_status,
    _check_and_complete_all_jobs,
    _get_record_owner_users,
    _get_sibling_jobs,
    _is_record_owned_by_user,
)


class ReviewJobView(LoginRequiredMixin, HorillaView):
    """Main page for logged-in user's review jobs."""

    nav_url = reverse_lazy("reviews:review_job_navbar_view")
    list_url = reverse_lazy("reviews:review_job_list_view")


@method_decorator(htmx_required, name="dispatch")
class ReviewJobNavbar(LoginRequiredMixin, HorillaNavView):
    """Navbar for review jobs."""

    nav_title = _("My Review Jobs")
    search_url = reverse_lazy("reviews:review_job_list_view")
    main_url = reverse_lazy("reviews:review_job_view")
    filterset_class = ReviewJobFilter
    all_view_types = False
    recently_viewed_option = False
    filter_option = False
    one_view_only = True
    reload_option = False
    border_enabled = False


@method_decorator(htmx_required, name="dispatch")
class ReviewJobListView(LoginRequiredMixin, HorillaListView):
    """List of review jobs assigned to current user."""

    model = ReviewJob
    view_id = "review-job-list"
    search_url = reverse_lazy("reviews:review_job_list_view")
    main_url = reverse_lazy("reviews:review_job_view")
    filterset_class = ReviewJobFilter
    save_to_list_option = False
    list_column_visibility = False
    bulk_select_option = False
    enable_sorting = False
    columns = ["reviews", "record", "status", "approvers"]

    def _owner_visible_job_ids(self, queryset):
        """Return job ids whose linked record was created by current user."""
        if not getattr(self.request.user, "id", None):
            return []

        ids = []
        for job in queryset:
            try:
                record = job.content_object
            except Exception:
                record = None
            if not record:
                continue
            if _is_record_owned_by_user(record, self.request.user):
                ids.append(job.id)
        return ids

    def get_queryset(self):
        base_qs = ReviewJob.all_objects.filter(
            is_active=True,
            status=ReviewJob.STATUS_PENDING,
        ).select_related("reviews", "content_type")
        owner_job_ids = self._owner_visible_job_ids(
            base_qs.exclude(assigned_to=self.request.user)
        )
        visible_qs = base_qs.filter(
            Q(assigned_to=self.request.user) | Q(id__in=owner_job_ids)
        )

        deduped_ids = []
        selected_by_key = {}
        for job in visible_qs.order_by("-created_at", "-id"):
            key = (
                job.reviews_id,
                job.content_type_id,
                job.object_id,
            )
            selected = selected_by_key.get(key)
            if selected is None:
                selected_by_key[key] = job
                continue

            # For each record/process key, prefer the current user's own assigned job
            # so approvers always get decision controls in the modal.
            selected_is_self = selected.assigned_to_id == getattr(
                self.request.user, "id", None
            )
            job_is_self = job.assigned_to_id == getattr(self.request.user, "id", None)
            if job_is_self and not selected_is_self:
                selected_by_key[key] = job

        for job in selected_by_key.values():
            deduped_ids.append(job.id)
        queryset = visible_qs.filter(id__in=deduped_ids).order_by("-created_at", "-id")
        if self.filterset_class:
            self.filterset = self.filterset_class(
                self.request.GET, queryset=queryset, request=self.request
            )
            queryset = self.filterset.filter_queryset(queryset)
        return queryset

    actions = [
        {
            "action": _("Review"),
            "src": "assets/icons/task.svg",
            "img_class": "w-4 h-4",
            "attrs": """
                        hx-get="{get_review_url}"
                        hx-target="#modalBox"
                        hx-swap="innerHTML"
                        onclick="openModal()"
                        """,
        },
    ]


@method_decorator(htmx_required, name="dispatch")
class ReviewJobDetailView(LoginRequiredMixin, TemplateView):
    """Approve or reject a review job in modal."""

    template_name = "reviews/review_job_modal.html"

    def _field_label(self, record, field_name):
        label = str(field_name).replace("_", " ").title()
        if record is not None:
            try:
                model_field = record._meta.get_field(field_name)
                verbose = getattr(model_field, "verbose_name", None)
                if verbose:
                    label = str(verbose).title()
            except Exception:
                pass
        return label

    def _notify(self, users, message, sender=None, instance=None):
        for user in users:
            if not getattr(user, "pk", None):
                continue
            create_notification(
                user=user,
                message=message,
                sender=sender,
                instance=instance,
            )

    def _can_view_job(self, job):
        user_id = getattr(self.request.user, "id", None)
        if not user_id:
            return False
        if job.assigned_to_id == user_id:
            return True
        record = getattr(job, "content_object", None)
        return _is_record_owned_by_user(record, self.request.user)

    def _build_record_details(self, record):
        """Build a compact, model-agnostic details list for the linked record."""
        if not record:
            return []

        details = []
        record_name = str(record).strip()

        skip_fields = {
            "id",
            "pk",
            "is_active",
            "additional_info",
            "company",
            "created_at",
            "created_by",
            "updated_at",
            "updated_by",
        }

        def _append_field(field):
            if len(details) >= 5:
                return
            field_name = getattr(field, "name", "")
            if not field_name or field_name in skip_fields:
                return
            display_getter = getattr(record, f"get_{field_name}_display", None)
            if callable(display_getter):
                value = display_getter()
            else:
                value = getattr(record, field_name, None)
                if isinstance(field, db_models.ForeignKey):
                    value = str(value) if value else None

            if value in (None, "", record_name):
                return

            label = getattr(field, "verbose_name", None) or field_name.replace("_", " ")
            details.append((str(label).title(), value))

        model_fields = list(record._meta.fields)

        # Prioritize identity-like fields first in a model-agnostic way.
        priority_keywords = ("name", "title", "subject", "code", "number", "reference")
        priority_fields = [
            f
            for f in model_fields
            if any(k in getattr(f, "name", "").lower() for k in priority_keywords)
        ]

        added_names = set()
        for field in priority_fields:
            _append_field(field)
            added_names.add(getattr(field, "name", ""))

        for field in model_fields:
            if getattr(field, "name", "") in added_names:
                continue
            _append_field(field)
            if len(details) >= 5:  # keep modal concise
                break

        return details

    def _build_field_values(self, job, record, sibling_jobs):
        """
        Return field rows with verbose label and AGGREGATED per-field review status.

        The status shown to the user is the aggregate across all approvers:
          - "approved"  → every approver approved this field
          - "rejected"  → at least one approver rejected this field
          - ""          → pending / not yet reviewed by everyone

        The comment shown is a combined string of all reviewers' comments.

        `can_inline_edit` is still scoped to the job owned by the record owner,
        and only shown when the aggregate status is "rejected".
        """
        snapshot = job.review_fields_snapshot or {}
        is_owner = _is_record_owned_by_user(record, self.request.user)
        rows = []
        for field_name, field_value in snapshot.items():
            label = self._field_label(record, field_name)
            agg_status = _aggregate_field_status(field_name, sibling_jobs)
            agg_comment = _aggregate_field_comment(field_name, sibling_jobs)
            rows.append(
                {
                    "key": field_name,
                    "label": label,
                    "value": field_value,
                    "status": agg_status,
                    "comment": agg_comment,
                    "can_inline_edit": (
                        agg_status == ReviewJob.STATUS_REJECTED
                        and is_owner
                        and job.status == ReviewJob.STATUS_PENDING
                    ),
                }
            )
        return rows

    def _build_modal_context(self, job):
        record = job.content_object
        sibling_jobs = _get_sibling_jobs(job)
        snapshot = job.review_fields_snapshot or {}

        # When the current user is an approver, show their own job's can_decide.
        # When they are the record owner viewing the modal, can_decide=False.
        can_decide = job.assigned_to_id == getattr(self.request.user, "id", None)

        # For the approver's modal, also surface how many parallel approvers exist.
        # "done" means this approver has personally approved ALL their assigned fields,
        # regardless of whether the overall job status has been flipped yet.
        total_approvers = len(sibling_jobs)
        snapshot_keys = list(snapshot.keys())

        def _approver_finished_all(sibling):
            """True if this approver has approved every field in their own job."""
            if sibling.status == ReviewJob.STATUS_APPROVED:
                return True
            if not snapshot_keys:
                return False
            field_reviews = (sibling.additional_info or {}).get("field_reviews") or {}
            return all(
                (field_reviews.get(k) or {}).get("status") == ReviewJob.STATUS_APPROVED
                for k in snapshot_keys
            )

        approvers_done = sum(1 for s in sibling_jobs if _approver_finished_all(s))

        return {
            "job": job,
            "can_decide": can_decide,
            "field_values": self._build_field_values(job, record, sibling_jobs),
            "record_details": self._build_record_details(record),
            "total_approvers": total_approvers,
            "approvers_done": approvers_done,
        }

    def get(self, request, *args, **kwargs):
        """Override get to handle missing/uninstalled content-type model gracefully."""
        try:
            return super().get(request, *args, **kwargs)
        except Exception:
            messages.error(
                request,
                _("The module for this review record is no longer available."),
            )
            return ScriptResponse(
                reload=True,
                close=True,
                msgs=True,
            )

    def get_context_data(self, **kwargs):
        """Build context with the review job details and approval status."""
        context = super().get_context_data(**kwargs)
        job = get_object_or_404(
            ReviewJob.all_objects.select_related("reviews"),
            pk=self.kwargs["pk"],
        )
        if not self._can_view_job(job):
            raise Http404
        context.update(self._build_modal_context(job))
        return context

    def post(self, request, *args, **kwargs):
        """
        post is only used for inline editing of rejected fields by the record owner
        """
        job = get_object_or_404(ReviewJob.all_objects, pk=self.kwargs["pk"])
        record = getattr(job, "content_object", None)

        action = (request.POST.get("action") or "").strip().lower()
        if action == "edit_rejected_field":
            if not _is_record_owned_by_user(record, request.user):
                return render(request, "403.html", {"modal": True})
            field_key = (request.POST.get("field_key") or "").strip()
            new_value = request.POST.get("field_value", "")

            sibling_jobs = _get_sibling_jobs(job)
            # Only allow editing if aggregate status is "rejected"
            if (
                _aggregate_field_status(field_key, sibling_jobs)
                != ReviewJob.STATUS_REJECTED
            ):
                return render(
                    request, self.template_name, self._build_modal_context(job)
                )

            if not hasattr(record, field_key):
                return render(request, "404.html", status=404)
            try:
                model_field = record._meta.get_field(field_key)
                if isinstance(model_field, db_models.ForeignKey):
                    if not str(new_value).strip():
                        setattr(record, field_key, None)
                    else:
                        rel_obj = model_field.related_model.objects.filter(
                            pk=new_value
                        ).first()
                        setattr(record, field_key, rel_obj)
                else:
                    parsed = model_field.to_python(new_value)
                    setattr(record, field_key, parsed)
                record.save(update_fields=[field_key, "updated_at"])
            except Exception as e:
                messages.error(request, _(str(e)))
                return ScriptResponse(reload=True)

            # Reset the field to "pending" in EVERY sibling job so all approvers
            # can re-review the corrected value.
            updated_val = getattr(record, field_key, None)
            updated_val_str = None if updated_val is None else str(updated_val)
            now = timezone.now()
            for sibling in sibling_jobs:
                info = dict(sibling.additional_info or {})
                field_reviews = dict(info.get("field_reviews") or {})
                meta = dict(field_reviews.get(field_key) or {})
                meta["status"] = ReviewJob.STATUS_PENDING
                meta["resubmitted_at"] = now.isoformat()
                meta["resubmitted_by_id"] = getattr(request.user, "id", None)
                field_reviews[field_key] = meta
                info["field_reviews"] = field_reviews
                snapshot = dict(sibling.review_fields_snapshot or {})
                snapshot[field_key] = updated_val_str
                sibling.additional_info = info
                sibling.review_fields_snapshot = snapshot
                sibling.save(
                    update_fields=[
                        "additional_info",
                        "review_fields_snapshot",
                        "updated_at",
                    ]
                )

            # Notify all approvers about the resubmission.
            if job.reviews.notify_on_submission:
                approvers_to_notify = [
                    s.assigned_to
                    for s in sibling_jobs
                    if getattr(s.assigned_to, "pk", None)
                ]
                self._notify(
                    approvers_to_notify,
                    _("%(owner)s resubmitted %(field)s in %(process)s for %(record)s.")
                    % {
                        "owner": str(request.user),
                        "field": self._field_label(record, field_key),
                        "process": str(job.reviews),
                        "record": str(record or "-"),
                    },
                    sender=request.user,
                    instance=record,
                )
            return render(request, self.template_name, self._build_modal_context(job))

        if job.assigned_to_id != getattr(request.user, "id", None):
            return render(request, "403.html", {"modal": True})
        return render(request, self.template_name, self._build_modal_context(job))


@method_decorator(htmx_required, name="dispatch")
class ReviewJobFieldReviewView(LoginRequiredMixin, TemplateView):
    """Field-level review modal for a single field in a review job."""

    template_name = "reviews/review_job_field_modal.html"

    def _field_label(self, record, field_key):
        label = str(field_key).replace("_", " ").title()
        if record is not None:
            try:
                model_field = record._meta.get_field(field_key)
                verbose = getattr(model_field, "verbose_name", None)
                if verbose:
                    label = str(verbose).title()
            except Exception:
                pass
        return label

    def _notify(self, users, message, sender=None, instance=None):
        for user in users:
            if not getattr(user, "pk", None):
                continue
            create_notification(
                user=user,
                message=message,
                sender=sender,
                instance=instance,
            )

    def _get_job(self):
        return get_object_or_404(ReviewJob.all_objects, pk=self.kwargs["pk"])

    def _build_field_context(self, job, field_key):
        snapshot = job.review_fields_snapshot or {}
        if field_key not in snapshot:
            raise Http404
        record = job.content_object
        label = self._field_label(record, field_key)

        # Show THIS approver's own decision in the field modal (not the aggregate),
        # so they can see what they personally chose and change it if needed.
        field_reviews = (job.additional_info or {}).get("field_reviews") or {}
        current = field_reviews.get(field_key, {}) or {}

        # Also compute aggregate so we can show a hint if another approver already rejected.
        sibling_jobs = _get_sibling_jobs(job)
        agg_status = _aggregate_field_status(field_key, sibling_jobs)

        return {
            "job": job,
            "field_key": field_key,
            "field_label": label,
            "field_value": snapshot.get(field_key),
            "field_status": current.get("status", ""),
            "field_comment": current.get("comment", ""),
            "agg_status": agg_status,
            "total_approvers": len(sibling_jobs),
        }

    def get_context_data(self, **kwargs):
        """
        fucntion is only used for showing the field review modal for approvers
        """
        context = super().get_context_data(**kwargs)
        job = self._get_job()
        if job.assigned_to_id != getattr(self.request.user, "id", None):
            raise Http404
        field_key = (self.request.GET.get("field") or "").strip()
        context.update(self._build_field_context(job, field_key))
        return context

    def post(self, request, *args, **kwargs):
        """Handle approve/reject decision for a single field in this review job."""
        job = self._get_job()
        if job.assigned_to_id != getattr(request.user, "id", None):
            return render(request, "403.html", {"modal": True})
        field_key = (request.POST.get("field_key") or "").strip()
        decision = (request.POST.get("field_decision") or "").strip().lower()

        if decision not in (ReviewJob.STATUS_APPROVED, ReviewJob.STATUS_REJECTED):
            messages.error(request, _("Invalid decision."))
            return ScriptResponse(reload=True, msgs=True)

        if field_key not in (job.review_fields_snapshot or {}):
            return render(request, "404.html", status=404)

        # Save THIS approver's decision on their own job.
        info = dict(job.additional_info or {})
        field_reviews = dict(info.get("field_reviews") or {})
        field_reviews[field_key] = {
            "status": decision,
            "comment": request.POST.get("field_comment", "").strip(),
            "reviewed_by_id": request.user.id,
            "reviewed_at": timezone.now().isoformat(),
        }
        info["field_reviews"] = field_reviews
        job.additional_info = info
        job.save(update_fields=["additional_info", "updated_at"])

        # Check if THIS approver has now approved ALL their fields.
        snapshot_keys = list((job.review_fields_snapshot or {}).keys())
        this_approver_all_approved = snapshot_keys and all(
            (field_reviews.get(k, {}) or {}).get("status") == ReviewJob.STATUS_APPROVED
            for k in snapshot_keys
        )

        record = job.content_object
        owners = _get_record_owner_users(record)
        label = self._field_label(record, field_key)

        # Send per-field notifications.
        if decision == ReviewJob.STATUS_APPROVED and job.reviews.notify_on_approval:
            self._notify(
                owners,
                _(
                    "%(field)s was approved in %(process)s by %(approver)s. Comment: %(comment)s"
                )
                % {
                    "field": label,
                    "process": str(job.reviews),
                    "approver": str(request.user),
                    "comment": request.POST.get("field_comment", "").strip() or "-",
                },
                sender=request.user,
                instance=record,
            )
        if decision == ReviewJob.STATUS_REJECTED and job.reviews.notify_on_rejection:
            self._notify(
                owners,
                _(
                    "%(field)s was rejected in %(process)s by %(approver)s. Reason: %(comment)s"
                )
                % {
                    "field": label,
                    "process": str(job.reviews),
                    "approver": str(request.user),
                    "comment": request.POST.get("field_comment", "").strip() or "-",
                },
                sender=request.user,
                instance=record,
            )

        # Only attempt global completion if this approver just finished all their fields.
        all_jobs_completed = False
        if this_approver_all_approved:
            all_jobs_completed = _check_and_complete_all_jobs(
                job, request.user, request
            )

        if all_jobs_completed:
            messages.success(
                request,
                _(
                    "All approvers have approved all review fields. Review completed successfully."
                ),
            )
            return ScriptResponse(
                extra="closeDetailModal();",
                close=True,
                reload=True,
                msgs=True,
            )

        # If this approver finished all their fields but others haven't yet,
        # show a friendly message and close the field modal.
        if this_approver_all_approved:
            messages.info(
                request,
                _(
                    "You have approved all fields. Waiting for other approvers to complete their review."
                ),
            )
            detail_url = reverse(
                "reviews:review_job_detail_view",
                kwargs={"pk": job.pk},
            )
            return HttpResponse(
                "<script>"
                "closeDetailModal();"
                f"htmx.ajax('GET', '{detail_url}', {{target:'#modalBox', swap:'innerHTML'}});"
                "$('#reloadMessagesButton').click();"
                "</script>"
            )

        detail_url = reverse(
            "reviews:review_job_detail_view",
            kwargs={"pk": job.pk},
        )
        return HttpResponse(
            "<script>"
            "closeDetailModal();"
            f"htmx.ajax('GET', '{detail_url}', {{target:'#modalBox', swap:'innerHTML'}});"
            "</script>"
        )
