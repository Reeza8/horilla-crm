"""
Jobs detail views for the approvals app.
"""

# Standard library imports
import threading
from datetime import timedelta

# Third-party imports (Django)
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import close_old_connections
from django.template import Context, Template
from django.views.generic import TemplateView

from horilla.auth.models import User
from horilla.contrib.activity.models import Activity
from horilla.contrib.mail.models import (
    HorillaMail,
    HorillaMailConfiguration,
    HorillaMailTemplate,
)
from horilla.contrib.mail.services import HorillaMailManager
from horilla.contrib.notifications.methods import create_notification
from horilla.contrib.notifications.models import NotificationTemplate
from horilla.contrib.utils.middlewares import _thread_local
from horilla.db import transaction
from horilla.db.models import Q
from horilla.shortcuts import get_object_or_404
from horilla.urls import reverse_lazy

# First party imports (Horilla)
from horilla.utils import timezone
from horilla.utils.decorators import htmx_required, method_decorator
from horilla.utils.translation import gettext_lazy as _
from horilla.web import HttpNotFound, HttpResponse, HttpResponseRedirect, ScriptResponse

# Local imports
from ..models import ApprovalDecision, ApprovalInstance
from ..utils import (
    get_cycle_started_at,
    get_next_user_step,
    get_pending_user_steps,
    get_user_pending_step,
    get_waiting_policy,
    get_who_should_approve_config,
    is_user_pending_approver,
    notify_current_approvers,
    safe_content_object,
)


class ApprovalJobReviewView(LoginRequiredMixin, TemplateView):
    """Approve/reject a pending approval instance in full-page detail view."""

    template_name = "approval_job_detail.html"

    def get_template_names(self):
        """Always use the HTMX fragment — direct loads are redirected in get()."""
        return [self.template_name]

    @staticmethod
    def _build_record_details(record, editable_fields=None):
        """Build model-agnostic record details for full-page display."""
        if not record:
            return []
        all_editable = editable_fields is None
        editable_fields = set(editable_fields or [])

        details = []
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

        for field in record._meta.fields:
            if getattr(field, "name", "") in skip_fields:
                continue

            field_name = field.name
            display_getter = getattr(record, f"get_{field_name}_display", None)
            if callable(display_getter):
                value = display_getter()
            else:
                value = getattr(record, field_name, None)
                if getattr(field, "many_to_one", False):
                    value = str(value) if value else None

            label = getattr(field, "verbose_name", None) or field_name.replace("_", " ")
            field_type = getattr(field, "get_internal_type", lambda: "")()
            input_type = "text"
            choices = []
            raw_value = getattr(record, field_name, None)
            if getattr(field, "many_to_one", False):
                input_type = "select"
                rel_model = getattr(field, "related_model", None)
                if rel_model is not None:
                    try:
                        choices = [
                            {"value": str(obj.pk), "label": str(obj)}
                            for obj in rel_model.objects.all()[:200]
                        ]
                    except Exception:
                        choices = []
                raw_value = getattr(record, f"{field_name}_id", None)
            elif getattr(field, "choices", None):
                input_type = "select"
                choices = [
                    {"value": str(c[0]), "label": str(c[1])}
                    for c in (field.choices or [])
                ]
            elif field_type in ("DateField",):
                input_type = "date"
            elif field_type in ("DateTimeField",):
                input_type = "datetime-local"
            elif field_type in (
                "IntegerField",
                "BigIntegerField",
                "PositiveIntegerField",
                "SmallIntegerField",
                "DecimalField",
                "FloatField",
            ):
                input_type = "number"
            elif field_type == "BooleanField":
                input_type = "checkbox"

            details.append(
                {
                    "name": field_name,
                    "label": str(label).title(),
                    "display": value if value not in (None, "") else "-",
                    "raw_value": "" if raw_value is None else raw_value,
                    "editable": all_editable or field_name in editable_fields,
                    "input_type": input_type,
                    "choices": choices,
                }
            )

        return details

    @staticmethod
    def _detail_tab_body(record):
        """Return fields for shared details-tab renderer."""
        if not record:
            return []
        excluded = {
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
        body = []
        for field in record._meta.fields:
            if field.name in excluded:
                continue
            if hasattr(field, "editable") and not field.editable:
                continue
            body.append((field.verbose_name, field.name))
        return body

    @staticmethod
    def _editable_fields_for_job(job):
        policy = get_waiting_policy(job)
        scope = policy.get("scope", "no_fields")
        if scope == "all_fields":
            return None  # None means all editable
        if scope == "specific_fields":
            return set(policy.get("fields", []) or [])
        return set()

    def _next_step(self, instance):
        return get_next_user_step(instance.current_step, instance=instance)

    @staticmethod
    def _related_tasks(job):
        try:
            related_object_id = int(job.object_id)
        except Exception:
            return Activity.objects.none()
        return (
            Activity.objects.filter(
                content_type=job.content_type,
                object_id=related_object_id,
                activity_type="task",
            )
            .order_by("-created_at", "-id")
            .distinct()
        )

    def get(self, request, *args, **kwargs):
        """Redirect to history if the approval is no longer pending."""
        base_url = reverse_lazy("approvals:approval_job_view")
        is_htmx = request.headers.get("HX-Request") == "true"
        job = ApprovalInstance.objects.filter(pk=self.kwargs["pk"]).first()

        if job is None:
            messages.warning(
                request,
                str(_("This approval no longer exists.")),
            )
            if is_htmx:
                resp = HttpResponse()
                resp["HX-Redirect"] = f"{base_url}?section=my_jobs"
                return resp
            return HttpResponse(
                f'<html><body><script>window.location.replace("{base_url}?section=my_jobs");</script></body></html>'
            )

        # Direct (non-HTMX) page loads can't render the fragment properly.
        if not is_htmx:
            return HttpResponse(
                f'<html><body><script>window.location.replace("{base_url}?section=my_jobs");</script></body></html>'
            )

        if job.status != "pending":
            return HttpResponseRedirect(job.get_history_url())

        if safe_content_object(job) is None and job.content_type:
            job.delete()
            messages.warning(
                request,
                str(
                    _(
                        "Module not found: the linked record no longer exists. The approval entry has been removed."
                    )
                ),
            )
            resp = HttpResponse()
            resp["HX-Redirect"] = f"{base_url}?section=my_jobs"
            return resp

        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        """Build context with the approval job, steps, and user permissions."""
        context = super().get_context_data(**kwargs)
        job = get_object_or_404(
            ApprovalInstance.objects.select_related(
                "rule", "current_step", "content_type"
            ),
            pk=self.kwargs["pk"],
            status="pending",
        )
        if not is_user_pending_approver(job, self.request.user):
            raise HttpNotFound(_("You are not an approver for this job."))
        policy = get_waiting_policy(job)
        record = safe_content_object(job)
        editable_fields = self._editable_fields_for_job(job)
        process_rule = getattr(job.current_step, "approval_process_rule", None)
        total_steps = 0
        completed_steps = 0
        current_step_order = None
        if process_rule:
            user_steps_qs = (
                process_rule.steps.filter(is_active=True)
                .filter(
                    Q(approver_type="user", approver_user__isnull=False)
                    | (Q(approver_type="role") & ~Q(role_identifier=""))
                )
                .order_by("order", "id")
            )
            step_orders = list(user_steps_qs.values_list("order", flat=True))
            total_steps = len(step_orders)
            who_cfg = get_who_should_approve_config(process_rule)
            approved_steps_count = (
                ApprovalDecision.objects.filter(
                    instance=job,
                    decision="approve",
                    step__approval_process_rule=process_rule,
                )
                .filter(
                    **(
                        {"decided_at__gte": get_cycle_started_at(job)}
                        if get_cycle_started_at(job)
                        else {}
                    )
                )
                .values("step_id")
                .distinct()
                .count()
            )
            if who_cfg.get("approval_order") == "parallel":
                completed_steps = approved_steps_count
                pending_steps = get_pending_user_steps(job)
                current_step_order = pending_steps[0].order if pending_steps else None
            elif job.current_step_id:
                current_step_order = job.current_step.order
                completed_steps = len(
                    [o for o in step_orders if o < current_step_order]
                )
            elif job.status == "approved":
                completed_steps = total_steps
            else:
                completed_steps = approved_steps_count
            if job.status == "approved":
                completed_steps = total_steps
        context["job"] = job
        context["record"] = record
        context["record_details"] = self._build_record_details(
            record,
            editable_fields=None if editable_fields is None else editable_fields,
        )
        body = self._detail_tab_body(record)
        field_permissions = {}
        editable_now = job.status == "pending"
        for _label, field_name in body:
            if not editable_now:
                field_permissions[field_name] = "readonly"
                continue
            if editable_fields is None:
                field_permissions[field_name] = "readwrite"
            elif field_name in editable_fields:
                field_permissions[field_name] = "readwrite"
            else:
                field_permissions[field_name] = "readonly"
        context["obj"] = record
        context["body"] = body
        context["field_permissions"] = field_permissions
        context["app_label"] = record._meta.app_label if record else ""
        context["model_name"] = record._meta.model_name if record else ""
        context["edit_field"] = True
        context["non_editable_fields"] = []
        context["can_update"] = editable_now
        context["pipeline_field"] = None
        context["editable_scope"] = policy.get("scope", "no_fields")
        context["editable_fields"] = policy.get("fields", []) or []
        context["total_steps"] = total_steps
        context["completed_steps"] = completed_steps
        context["current_step_order"] = current_step_order
        context["delegate_users"] = User.objects.filter(is_active=True).exclude(
            id=self.request.user.id
        )[:200]
        context["tab_url"] = reverse_lazy(
            "approvals:approval_job_detail_tab_view",
            kwargs={"pk": job.pk},
        )
        return context

    def post(self, request, *args, **kwargs):
        """Kept for backward compatibility; decisions now use modal view."""
        return HttpResponse(
            f"<script>htmx.ajax('GET', '{reverse_lazy('approvals:approval_job_respond_modal_view', kwargs={'pk': self.kwargs['pk']})}',"
            "{target:'#modalBox',swap:'innerHTML'});openModal();</script>"
        )


@method_decorator(htmx_required, name="dispatch")
class ApprovalJobRespondModalView(LoginRequiredMixin, TemplateView):
    """Respond (approve/reject/delegate) in modal."""

    template_name = "approval_job_respond_modal.html"

    def get_context_data(self, **kwargs):
        """Build context with the pending approval job for the respond modal."""
        context = super().get_context_data(**kwargs)
        job = get_object_or_404(
            ApprovalInstance.objects.select_related("rule", "current_step"),
            pk=self.kwargs["pk"],
            status="pending",
        )
        if not is_user_pending_approver(job, self.request.user):
            raise HttpNotFound(_("You are not an approver for this job."))
        context["job"] = job
        context["delegate_users"] = User.objects.filter(is_active=True).exclude(
            id=self.request.user.id
        )
        return context

    @staticmethod
    def _next_step(instance):
        return get_next_user_step(instance.current_step, instance=instance)

    @staticmethod
    def _set_record_field_value(record, field_name, raw_value):
        """Type-safe setter for model fields used by action config."""
        field = record._meta.get_field(field_name)
        if getattr(field, "many_to_one", False):
            setattr(record, f"{field_name}_id", raw_value or None)
            return
        internal_type = getattr(field, "get_internal_type", lambda: "")()
        if internal_type == "BooleanField":
            setattr(
                record,
                field_name,
                (
                    (str(raw_value).lower() in ("1", "true", "yes", "on"))
                    if raw_value not in (None, "")
                    else None
                ),
            )
            return
        try:
            setattr(record, field_name, field.to_python(raw_value))
        except Exception:
            setattr(record, field_name, raw_value)

    @classmethod
    def _apply_action_update_field(cls, job, action_side, request=None):
        """
        Apply configured update-field action to target record.
        action_side: 'approval' or 'rejection'
        """
        step = getattr(job, "current_step", None)
        if not step:
            return
        process_rule = getattr(step, "approval_process_rule", None)
        if not process_rule:
            return
        cfg = process_rule.rule_config or {}
        selected_actions = [
            a.strip()
            for a in (cfg.get(f"{action_side}_actions") or "").split(",")
            if a.strip()
        ]
        if "update_field" not in selected_actions:
            return
        action_cfg = cfg.get(f"{action_side}_action_config", {}) or {}
        field_name = (action_cfg.get("update_field") or "").strip()
        field_value = action_cfg.get("update_value")
        if not field_name:
            return
        record = safe_content_object(job)
        if record is None:
            if request:
                messages.error(
                    request,
                    str(
                        _(
                            "Module not found: the record linked to this approval no longer exists."
                        )
                    ),
                )
            return
        try:
            setattr(_thread_local, "skip_approval_edit_guard", True)
            setattr(_thread_local, "skip_approval_sync", True)
            cls._set_record_field_value(record, field_name, field_value)
            record.save()
        except Exception:
            # Keep workflow resilient: failure in side-effect should not break decision logging.
            pass
        finally:
            setattr(_thread_local, "skip_approval_edit_guard", False)
            setattr(_thread_local, "skip_approval_sync", False)

    @staticmethod
    def _resolve_expression_email(expr, record, request_user):
        """Resolve email expression (self/instance.*) to concrete addresses."""
        expr = (expr or "").strip()
        if not expr:
            return []
        if expr == "self":
            email = getattr(request_user, "email", None)
            return [email] if email else []
        if expr.startswith("instance."):
            value = record
            for part in expr.split(".")[1:]:
                value = getattr(value, part, None)
                if value is None:
                    break
            if isinstance(value, User):
                email = getattr(value, "email", None)
                return [email] if email else []
            return [value] if isinstance(value, str) and "@" in value else []
        return [expr] if "@" in expr else []

    @staticmethod
    def _render_notification_message_text(raw, context_dict):
        if not (raw or "").strip():
            return ""
        try:
            return Template(raw).render(Context(context_dict))
        except Exception:
            return raw

    @staticmethod
    def _resolve_expression_user(expr, record, request_user):
        """Resolve self / instance.* / user id / email to User objects."""
        expr = (expr or "").strip()
        if not expr:
            return []
        if expr == "self":
            return [request_user] if getattr(request_user, "pk", None) else []
        if expr.startswith("instance."):
            value = record
            for part in expr.split(".")[1:]:
                if value is None:
                    return []
                value = getattr(value, part, None)
            if value is None:
                return []
            if isinstance(value, User):
                return [value] if getattr(value, "is_active", True) else []
            if isinstance(value, str) and "@" in value:
                u = User.objects.filter(
                    email__iexact=value.strip(), is_active=True
                ).first()
                return [u] if u else []
            return []
        if expr.isdigit():
            u = User.objects.filter(pk=int(expr), is_active=True).first()
            return [u] if u else []
        if "@" in expr:
            u = User.objects.filter(email__iexact=expr.strip(), is_active=True).first()
            return [u] if u else []
        return []

    @classmethod
    def _collect_notification_recipient_users(cls, action_cfg, record, request_user):
        recipients = set()
        notification_to_expr = (action_cfg.get("notification_to") or "").strip()
        if notification_to_expr:
            for token in [
                x.strip() for x in notification_to_expr.split(",") if x.strip()
            ]:
                for u in cls._resolve_expression_user(token, record, request_user):
                    if u:
                        recipients.add(u)
        also_sent = action_cfg.get("notification_also_sent_to", []) or []
        if isinstance(also_sent, str):
            also_sent = [x.strip() for x in also_sent.split(",") if x.strip()]
        for token in also_sent:
            t = str(token).strip()
            if not t:
                continue
            if t.isdigit():
                u = User.objects.filter(pk=int(t), is_active=True).first()
                if u:
                    recipients.add(u)
                continue
            for u in cls._resolve_expression_user(t, record, request_user):
                if u:
                    recipients.add(u)
        legacy = (action_cfg.get("notification_users") or "").strip()
        if legacy and not notification_to_expr and not also_sent:
            for uid in [x.strip() for x in legacy.split(",") if x.strip()]:
                if uid.isdigit():
                    u = User.objects.filter(pk=int(uid), is_active=True).first()
                    if u:
                        recipients.add(u)
        return recipients

    @classmethod
    def _apply_action_assign_task(cls, job, action_side, request_user):
        step = getattr(job, "current_step", None)
        process_rule = getattr(step, "approval_process_rule", None) if step else None
        if not process_rule:
            return
        cfg = process_rule.rule_config or {}
        action_cfg = cfg.get(f"{action_side}_action_config", {}) or {}
        title = (action_cfg.get("task_title") or "").strip()
        description = (action_cfg.get("task_description") or "").strip()
        payload = action_cfg.get("task_payload", {}) or {}
        record = safe_content_object(job)
        if record is None:
            return
        due_datetime = None
        try:
            due_days = int((payload.get("due_days") or "").strip())
            due_datetime = timezone.now() + timedelta(days=due_days)
        except Exception:
            due_datetime = None
        status = (payload.get("status") or "not_started").strip() or "not_started"
        priority = (payload.get("priority") or "").strip() or None
        try:
            object_id = int(job.object_id)
        except Exception:
            return
        task = Activity.objects.create(
            subject=title or f"{action_side.title()} task",
            description=description or None,
            activity_type="task",
            content_type=job.content_type,
            object_id=object_id,
            status=status,
            task_priority=priority,
            due_datetime=due_datetime,
            owner=request_user,
            company=getattr(job, "company", None),
            created_by=request_user,
            updated_by=request_user,
        )
        task.assigned_to.add(request_user)

    @classmethod
    def _apply_action_mail(cls, job, action_side, request_user):
        step = getattr(job, "current_step", None)
        process_rule = getattr(step, "approval_process_rule", None) if step else None
        if not process_rule:
            return
        cfg = process_rule.rule_config or {}
        action_cfg = cfg.get(f"{action_side}_action_config", {}) or {}
        record = safe_content_object(job)
        if record is None:
            return

        recipients = set()
        email_to_expr = (action_cfg.get("email_to") or "").strip()
        if email_to_expr:
            for token in [x.strip() for x in email_to_expr.split(",") if x.strip()]:
                for email in cls._resolve_expression_email(token, record, request_user):
                    recipients.add(email)
        also_sent = action_cfg.get("email_also_sent_to", []) or []
        if isinstance(also_sent, str):
            also_sent = [x.strip() for x in also_sent.split(",") if x.strip()]
        for token in also_sent:
            for email in cls._resolve_expression_email(
                str(token), record, request_user
            ):
                recipients.add(email)
        if not recipients:
            return

        subject = (action_cfg.get("email_subject") or "").strip()
        body = (action_cfg.get("email_body") or "").strip()
        template_id = (action_cfg.get("email_template_id") or "").strip()
        if template_id:
            template = HorillaMailTemplate.objects.filter(pk=template_id).first()
            if template:
                subject = subject or (template.subject or "")
                body = body or (template.body or "")

        sender = (
            HorillaMailConfiguration.objects.filter(
                is_primary=True,
                mail_channel="outgoing",
            ).first()
            or HorillaMailConfiguration.objects.filter(
                mail_channel="outgoing",
            ).first()
        )
        if not sender:
            return
        try:
            object_id = int(job.object_id)
        except Exception:
            return
        mail = HorillaMail.objects.create(
            sender=sender,
            to=",".join(sorted(recipients)),
            subject=subject or f"{action_side.title()} notification",
            body=body or "",
            content_type=job.content_type,
            object_id=object_id,
            mail_status="draft",
            company=getattr(job, "company", None),
            created_by=request_user,
            updated_by=request_user,
        )
        mail_pk = mail.pk
        user_pk = request_user.pk

        def _send_mail_worker():
            close_old_connections()
            try:
                mail_obj = HorillaMail.objects.select_related(
                    "content_type", "company", "sender"
                ).get(pk=mail_pk)
                user = User.objects.get(pk=user_pk)
                rec = None
                try:
                    if mail_obj.content_type_id and mail_obj.object_id:
                        rec = mail_obj.content_type.get_object_for_this_type(
                            pk=mail_obj.object_id
                        )
                except Exception:
                    rec = None
                ctx = {
                    "instance": rec,
                    "user": user,
                    "active_company": getattr(mail_obj, "company", None),
                    "request": getattr(_thread_local, "request", None),
                }
                HorillaMailManager.send_mail(mail_obj, context=ctx)
            finally:
                close_old_connections()

        transaction.on_commit(
            lambda: threading.Thread(
                target=_send_mail_worker,
                daemon=True,
                name="horilla-approval-action-mail",
            ).start()
        )

    @classmethod
    def _run_configured_actions(cls, job, action_side, request_user, request=None):
        """Execute configured side-effects for approval/rejection."""
        step = getattr(job, "current_step", None)
        process_rule = getattr(step, "approval_process_rule", None) if step else None
        if not process_rule:
            return
        cfg = process_rule.rule_config or {}
        actions_raw = (cfg.get(f"{action_side}_actions") or "").strip()
        if not actions_raw:
            return
        actions = [a.strip() for a in actions_raw.split(",") if a.strip()]
        if "update_field" in actions:
            cls._apply_action_update_field(job, action_side, request=request)
        if "assign_task" in actions:
            cls._apply_action_assign_task(job, action_side, request_user)
        if "mail" in actions:
            cls._apply_action_mail(job, action_side, request_user)
        if "notification" in actions:
            cls._apply_action_notification(job, action_side, request_user)

    @classmethod
    def _apply_action_notification(cls, job, action_side, request_user):
        step = getattr(job, "current_step", None)
        process_rule = getattr(step, "approval_process_rule", None) if step else None
        if not process_rule:
            return
        cfg = process_rule.rule_config or {}
        action_cfg = dict(cfg.get(f"{action_side}_action_config", {}) or {})
        record = safe_content_object(job)
        recipients = cls._collect_notification_recipient_users(
            action_cfg, record, request_user
        )
        if not recipients:
            return
        job_pk = job.pk
        sender_pk = request_user.pk
        recipient_pks = [u.pk for u in recipients]

        def _notify_worker():
            close_old_connections()
            try:
                inst = ApprovalInstance.objects.select_related(
                    "rule", "content_type", "company"
                ).get(pk=job_pk)
                record_inner = safe_content_object(inst)
                sender = User.objects.get(pk=sender_pk)
                users = list(User.objects.filter(pk__in=recipient_pks, is_active=True))
                template_id = (action_cfg.get("notification_template_id") or "").strip()
                override = (action_cfg.get("notification_message") or "").strip()
                tmpl = None
                if template_id:
                    tmpl = NotificationTemplate.objects.filter(pk=template_id).first()
                base_msg = (tmpl.message if tmpl else "") or ""
                msg_raw = override or base_msg
                if not (msg_raw or "").strip():
                    record_label = (
                        str(record_inner)
                        if record_inner is not None
                        else str(inst.object_id)
                    )
                    msg_raw = f"{action_side.title()} notification for {record_label}"
                ctx = {
                    "instance": record_inner,
                    "record": record_inner,
                    "job": inst,
                    "approval_instance": inst,
                    "user": sender,
                    "active_company": getattr(inst, "company", None),
                }
                msg = cls._render_notification_message_text(msg_raw, ctx)
                for user in users:
                    create_notification(
                        user=user,
                        message=msg,
                        sender=sender,
                        url=inst.get_history_url(),
                        instance=record_inner,
                        read=False,
                    )
            finally:
                close_old_connections()

        transaction.on_commit(
            lambda: threading.Thread(
                target=_notify_worker,
                daemon=True,
                name="horilla-approval-action-notification",
            ).start()
        )

    def _reload_response(self):
        """Close the respond modal and reload the job list, showing any queued messages."""
        list_url = reverse_lazy("approvals:approval_job_view")
        return ScriptResponse(
            extra=(
                f"htmx.ajax('GET', '{list_url}?section=my_jobs',"
                "{target:'#mainContent',select:'#mainContent',swap:'outerHTML'});"
            ),
            close=True,
            msgs=True,
        )

    def post(self, request, *args, **kwargs):
        """Process approve, reject, or delegate decisions submitted from the job review page."""
        job = get_object_or_404(
            ApprovalInstance.objects.select_related("current_step"),
            pk=self.kwargs["pk"],
            status="pending",
        )
        if not is_user_pending_approver(job, request.user):
            messages.error(request, _("You are not the approver for this job."))
            return self._reload_response()
        decision = (request.POST.get("decision") or "").strip().lower()
        if decision not in ("approve", "reject", "delegate"):
            messages.error(request, _("Invalid decision."))
            return self._reload_response()

        acting_step = get_user_pending_step(job, request.user)
        if decision in ("approve", "reject") and not acting_step:
            messages.error(request, _("No pending step found."))
            return self._reload_response()

        if decision in ("approve", "reject"):
            ApprovalDecision.objects.create(
                instance=job,
                step=acting_step,
                decided_by=request.user,
                decision=decision,
                comment=request.POST.get("review_note", ""),
                company=getattr(job, "company", None),
                created_by=request.user,
                updated_by=request.user,
            )

        if decision == "delegate":
            if not acting_step:
                messages.error(request, _("No pending step found."))
                return self._reload_response()
            delegate_user_id = request.POST.get("delegate_user")
            delegate_user = get_object_or_404(
                User.objects.filter(is_active=True),
                pk=delegate_user_id,
            )
            # Scope the delegation to this instance only: override who may act on
            # the current step, without creating/deleting ApprovalStep rows on the
            # shared ApprovalProcessRule (that would affect every other instance).
            job.delegated_approver = delegate_user
            job.updated_by = request.user
            job.save(update_fields=["delegated_approver", "updated_by", "updated_at"])
            messages.success(request, _("Approval delegated successfully."))
            return self._reload_response()

        if decision == "reject":
            self._run_configured_actions(
                job, "rejection", request.user, request=request
            )
            job.status = "rejected"
            job.delegated_approver = None
            job.updated_by = request.user
            job.save(
                update_fields=[
                    "status",
                    "delegated_approver",
                    "updated_by",
                    "updated_at",
                ]
            )
            messages.success(request, _("Approval rejected."))
        else:
            process_rule = getattr(job.current_step, "approval_process_rule", None)
            who_cfg = (
                get_who_should_approve_config(process_rule)
                if process_rule
                else {"overall_method": "anyone", "approval_order": "sequential"}
            )
            if who_cfg.get("approval_order") == "parallel":
                pending_steps = get_pending_user_steps(job)
                if pending_steps:
                    job.current_step = pending_steps[0]
                    job.delegated_approver = None
                    job.updated_by = request.user
                    job.save(
                        update_fields=[
                            "current_step",
                            "delegated_approver",
                            "updated_by",
                            "updated_at",
                        ]
                    )
                    messages.success(
                        request, _("Approved. Waiting for other approvers.")
                    )
                else:
                    self._run_configured_actions(
                        job, "approval", request.user, request=request
                    )
                    job.status = "approved"
                    job.current_step = None
                    job.delegated_approver = None
                    job.updated_by = request.user
                    job.save(
                        update_fields=[
                            "status",
                            "current_step",
                            "delegated_approver",
                            "updated_by",
                            "updated_at",
                        ]
                    )
                    messages.success(request, _("Approval completed."))
            else:
                next_step = self._next_step(job)
                if next_step:
                    job.current_step = next_step
                    job.delegated_approver = None
                    job.updated_by = request.user
                    job.save(
                        update_fields=[
                            "current_step",
                            "delegated_approver",
                            "updated_by",
                            "updated_at",
                        ]
                    )
                    notify_current_approvers(job, triggered_by=request.user)
                    messages.success(request, _("Approved and moved to next approver."))
                else:
                    self._run_configured_actions(
                        job, "approval", request.user, request=request
                    )
                    job.status = "approved"
                    job.current_step = None
                    job.delegated_approver = None
                    job.updated_by = request.user
                    job.save(
                        update_fields=[
                            "status",
                            "current_step",
                            "delegated_approver",
                            "updated_by",
                            "updated_at",
                        ]
                    )
                    messages.success(request, _("Approval completed."))

        list_url = reverse_lazy("approvals:approval_job_view")
        return ScriptResponse(
            extra=(
                f"htmx.ajax('GET', '{list_url}?section=my_jobs',"
                "{target:'#mainContent',select:'#mainContent',swap:'outerHTML'});"
            ),
            close=True,
            msgs=True,
        )
