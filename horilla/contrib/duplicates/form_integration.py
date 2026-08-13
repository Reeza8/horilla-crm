"""
Integration module to inject duplicate checking into Horilla form views.
This module patches HorillaSingleFormView and HorillaMultiStepFormView
to check for duplicates before saving.
Also injects Potential Duplicates tab into detail views.
"""

# Standard library imports
import logging
import uuid
from datetime import datetime as dt
from decimal import Decimal, InvalidOperation
from functools import wraps
from zoneinfo import ZoneInfo

# Third-party imports (Django)
from django.template.loader import render_to_string

from horilla.apps import apps
from horilla.contrib.core.models import HorillaContentType
from horilla.contrib.utils.middlewares import _thread_local
from horilla.db import models as db_models
from horilla.urls import reverse

# First party imports (Horilla)
from horilla.utils import timezone
from horilla.utils.translation import gettext_lazy as _
from horilla.web import HttpResponse, QueryDict

from .duplicate_checker import check_duplicates

# Local imports
from .models import DuplicateRule


def create_form_valid_with_duplicate_check(original_form_valid, is_multi_step=False):
    """
    Create a wrapped form_valid method that checks for duplicates before saving.

    Args:
        original_form_valid: The original form_valid method
        is_multi_step: Whether this is for multi-step form view
    """

    @wraps(original_form_valid)
    def form_valid_with_duplicate_check(self, form):
        # Skip duplicate checking if this is not the final step (for multi-step)
        if is_multi_step:
            # Get current step from POST data or view attribute
            step = int(self.request.POST.get("step", getattr(self, "current_step", 1)))
            total_steps = getattr(self, "total_steps", 1)
            if step < total_steps:
                # Not final step, proceed normally
                return original_form_valid(self, form)

        # Check if we should skip duplicate checking (e.g., if bypass flag is set)
        skip_check = (
            self.request.GET.get("skip_duplicate_check", "false").lower() == "true"
        )
        skip_check = (
            skip_check
            or self.request.POST.get("skip_duplicate_check", "false").lower() == "true"
        )
        if skip_check:
            # Set flag on request so we don't check again
            self.request.skip_duplicate_check = True
            return original_form_valid(self, form)

        # Only check duplicates if model is registered for duplicate checking
        if not hasattr(self, "model") or not self.model:
            return original_form_valid(self, form)

        # Check if model is registered for duplicate checking
        try:
            from horilla.registry.feature import FEATURE_REGISTRY

            duplicate_models = FEATURE_REGISTRY.get("duplicate_models", [])
            if self.model not in duplicate_models:
                return original_form_valid(self, form)
        except Exception:
            # If registry check fails, continue anyway
            pass

        # Skip duplicate check when the form only changes owner fields
        owner_fields = set(getattr(self.model, "OWNER_FIELDS", []))
        if owner_fields:
            form_fields = set(form.fields.keys())
            if form_fields and form_fields.issubset(owner_fields):
                return original_form_valid(self, form)

        # Create instance from form (before saving)
        instance = form.save(commit=False)

        try:
            if hasattr(self.request, "active_company"):
                instance.company = self.request.active_company
            elif hasattr(_thread_local, "request") and hasattr(
                _thread_local.request, "active_company"
            ):
                instance.company = _thread_local.request.active_company
            elif hasattr(self.request.user, "company"):
                instance.company = self.request.user.company
        except Exception:
            pass

        is_edit = bool(
            getattr(self, "object", None) and getattr(self.object, "pk", None)
        )
        if not is_edit:
            is_edit = bool(self.kwargs.get("pk"))
        if getattr(self, "duplicate_mode", False):
            is_edit = False
        try:
            duplicate_result = check_duplicates(instance, is_edit=is_edit)

            if duplicate_result.get("has_duplicates"):
                return get_duplicate_warning_response(
                    self.request,
                    duplicate_result,
                    form,
                    self,
                    original_form_valid,
                    is_multi_step,
                )
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.warning("Duplicate check failed: %s", e)

        return original_form_valid(self, form)

    return form_valid_with_duplicate_check


def get_duplicate_warning_response(
    request, duplicate_result, form, view, original_form_valid, is_multi_step
):
    """
    Generate HTMX response that opens horillaModal with duplicate warning.
    Returns the form HTML with script appended so the form stays visible.

    Args:
        request: HttpRequest
        duplicate_result: dict from check_duplicates()
        form: Form instance
        view: View instance
        original_form_valid: Original form_valid method to call after user confirms
        is_multi_step: Whether this is a multi-step form
    """
    # Serialize form data for re-submission
    form_data = {}
    for field_name in form.fields:
        if field_name in form.cleaned_data:
            value = form.cleaned_data[field_name]
            # Handle various field types
            if hasattr(value, "pk"):  # ForeignKey
                form_data[field_name] = value.pk
            elif hasattr(value, "__iter__") and not isinstance(
                value, str
            ):  # ManyToMany
                form_data[field_name] = [v.pk if hasattr(v, "pk") else v for v in value]
            else:
                form_data[field_name] = value

    # Also include POST data for file fields and other fields not in cleaned_data
    for key, value in request.POST.items():
        if key not in form_data and key != "csrfmiddlewaretoken":
            if key in request.POST.getlist(key):
                form_data[key] = request.POST.getlist(key)
            else:
                form_data[key] = value

    # Get form URL for continue button
    form_url = request.path
    query_params = request.GET.copy()
    query_params["skip_duplicate_check"] = "true"
    if query_params:
        form_url += "?" + query_params.urlencode()

    # Preserve save_and_new button value if it was clicked
    save_and_new_value = request.POST.get("save_and_new", "")

    # Store modal context in session for the view to retrieve
    session_key = f"duplicate_modal_{uuid.uuid4().hex[:16]}"
    request.session[session_key] = {
        "alert_title": duplicate_result.get(
            "alert_title", "Potential Duplicate Detected"
        ),
        "alert_message": duplicate_result.get(
            "alert_message", "Similar records were found. Do you want to proceed?"
        ),
        "duplicate_records": [
            (r.pk, str(r)) for r in duplicate_result.get("duplicate_records", [])[:10]
        ],
        "show_duplicate_records": duplicate_result.get("show_duplicate_records", True),
        "form_url": form_url,
        "model_name": (
            view.model._meta.model_name
            if hasattr(view, "model") and view.model
            else None
        ),
        "action": duplicate_result.get("action", "allow"),  # 'allow' or 'block'
        "save_and_new": save_and_new_value,  # Preserve save_and_new button value
    }
    request.session.modified = True

    modal_url = reverse(
        "duplicates:duplicate_warning_modal",
        kwargs={"session_key": session_key},
    )

    try:
        context = view.get_context_data(form=form)
        if is_multi_step:
            template_name = "form_view.html"
        else:
            template_name = view.template_name or "single_form_view.html"

        form_html = render_to_string(template_name, context, request=request)

        # Append HTMX div to form HTML to open duplicate modal
        htmx_content = f"""
        <div hx-get="{modal_url}"
             hx-target="#dynamicCreateModalBox"
             hx-trigger="load"
             hx-swap="innerHTML"
             hx-on::load="openDynamicModal();">
        </div>
        """

        return HttpResponse(form_html + htmx_content)
    except Exception as e:
        # Fallback to HTMX-only response if rendering fails
        logger = logging.getLogger(__name__)
        logger.warning("Error rendering form for duplicate warning: %s", str(e))
        htmx_content = f"""
        <div hx-get="{modal_url}"
             hx-target="#dynamicCreateModalBox"
             hx-trigger="load"
             hx-swap="innerHTML"
             hx-on::load="openDynamicModal();">
        </div>
        """
        return HttpResponse(htmx_content)


def create_prepare_tabs_with_duplicate_tab(original_prepare_tabs):
    """
    Create a wrapped _prepare_detail_tabs method that adds Potential Duplicates tab.

    Args:
        original_prepare_tabs: The original _prepare_detail_tabs method
    """

    @wraps(original_prepare_tabs)
    def _prepare_detail_tabs_with_duplicate_tab(self):
        # Call original _prepare_detail_tabs first; this sets self.object_id
        # and builds self.tabs with all standard tabs.
        original_prepare_tabs(self)

        # Check if we have an object_id (required for tabs)
        if not self.object_id:
            return
        try:
            # Get model from self if available
            model = None
            if hasattr(self, "model") and self.model:
                model = self.model
            else:
                duplicate_rule_content_types = DuplicateRule.objects.values_list(
                    "content_type", flat=True
                ).distinct()

                # Try each content type to see if object_id exists in that model
                for horilla_ct_id in duplicate_rule_content_types:
                    try:
                        horilla_ct = HorillaContentType.objects.get(pk=horilla_ct_id)
                        model_name = horilla_ct.model

                        # Find the model class
                        Model = None
                        for app_config in apps.get_app_configs():
                            try:
                                Model = apps.get_model(
                                    app_config.label, model_name.lower()
                                )
                                if Model:
                                    break
                            except (LookupError, ValueError):
                                continue

                        if Model:
                            # Check if object with this pk exists in this model
                            if Model.objects.filter(pk=self.object_id).exists():
                                model = Model
                                break
                    except Exception:
                        continue

            if not model:
                return

            # Check if model has duplicate rules and matching rules
            try:
                model_name = model._meta.model_name.lower()
                content_type = HorillaContentType.objects.filter(
                    model=model_name
                ).first()

                if not content_type:
                    return

                # Check if there are duplicate rules for this content type
                duplicate_rules = DuplicateRule.objects.filter(
                    content_type=content_type
                )
                if not duplicate_rules.exists():
                    return

                # Check if at least one duplicate rule has a matching rule
                has_matching_rule = False
                for dup_rule in duplicate_rules:
                    if dup_rule.matching_rule:
                        has_matching_rule = True
                        break

                if not has_matching_rule:
                    return

                django_content_type = HorillaContentType.objects.get_for_model(model)
                content_type_id = django_content_type.pk

                duplicates_url = reverse(
                    "duplicates:potential_duplicates_tab", kwargs={}
                )
                # Use QueryDict to properly construct URL with parameters
                params = QueryDict(mutable=True)
                params["object_id"] = self.object_id
                params["content_type_id"] = content_type_id
                duplicates_url = f"{duplicates_url}?{params.urlencode()}"

                # Add the tab to self.tabs
                if not hasattr(self, "tabs"):
                    self.tabs = []

                # Check if tab already exists
                tab_exists = any(
                    tab.get("id") == "potential-duplicates" for tab in self.tabs
                )
                if not tab_exists:
                    tab_data = {
                        "title": _("Potential Duplicates"),
                        "url": duplicates_url,
                        "target": "tab-potential-duplicates-content",
                        "id": "potential-duplicates",
                    }
                    self.tabs.append(tab_data)
            except Exception as e:
                # If any error occurs, just skip adding the tab
                logger = logging.getLogger(__name__)
                logger.debug(
                    "Could not add Potential Duplicates tab: %s", e, exc_info=True
                )
        except Exception:
            pass

    return _prepare_detail_tabs_with_duplicate_tab


def _apply_field_value_for_check(obj, field, field_name, request):
    """
    Apply the incoming POST value to obj in-memory without saving.
    Mirrors the type-handling logic from UpdateFieldView.post().
    Returns True on success, False if the value cannot be applied
    (caller should fall through to original_post for proper error handling).
    """

    try:
        if isinstance(field, db_models.ManyToManyField):
            return True

        value = request.POST.get(field_name)
        if value is None:
            return True  # nothing to apply; let original_post handle

        if isinstance(field, db_models.ForeignKey):
            if value == "":
                setattr(obj, field_name, None)
            else:
                related_obj = field.related_model.objects.get(pk=value)
                setattr(obj, field_name, related_obj)

        elif isinstance(field, db_models.BooleanField):
            if value == "":
                setattr(obj, field_name, None)
            else:
                setattr(obj, field_name, value == "True")

        elif isinstance(
            field,
            (
                db_models.IntegerField,
                db_models.BigIntegerField,
                db_models.SmallIntegerField,
            ),
        ):
            setattr(obj, field_name, int(value) if value else None)

        elif isinstance(field, db_models.DecimalField):
            try:
                setattr(obj, field_name, Decimal(value) if value else None)
            except InvalidOperation:
                return False

        elif isinstance(field, db_models.FloatField):
            setattr(obj, field_name, float(value) if value else None)

        elif isinstance(field, db_models.DateTimeField):
            if value:
                parsed = dt.fromisoformat(value)
                user = request.user
                if hasattr(user, "time_zone") and user.time_zone:
                    try:
                        parsed = parsed.replace(tzinfo=ZoneInfo(user.time_zone))
                        parsed = parsed.astimezone(timezone.get_default_timezone())
                    except Exception:
                        parsed = timezone.make_aware(
                            parsed, timezone.get_default_timezone()
                        )
                else:
                    parsed = timezone.make_aware(
                        parsed, timezone.get_default_timezone()
                    )
                setattr(obj, field_name, parsed)
            else:
                setattr(obj, field_name, None)

        elif isinstance(field, db_models.DateField):
            if value:
                setattr(obj, field_name, dt.fromisoformat(value).date())
            else:
                setattr(obj, field_name, None)

        else:
            setattr(obj, field_name, value)

        return True
    except Exception:
        return False


def _render_inline_edit_form(
    request, pk, field_name, app_label, model_name, obj, field
):
    """
    Re-render partials/edit_field.html so the edit form stays visible after a
    blocked/warned save. Uses EditFieldView.get_field_info() to build the context.
    The rendered form preserves the user's entered value via obj's in-memory state.
    """
    from horilla.contrib.generics.views.helpers.edit_field import get_edit_field_view

    edit_view = get_edit_field_view()
    field_info = edit_view.get_field_info(field, obj, request.user)
    context = {
        "object_id": pk,
        "field_info": field_info,
        "app_label": app_label,
        "model_name": model_name,
        "pipeline_field": None,
    }
    return render_to_string("partials/edit_field.html", context, request=request)


def _build_inline_duplicate_modal(request, duplicate_result, model, pk, rule_action):
    """
    Store duplicate warning data in session and return the HTMX modal-trigger snippet.
    rule_action is used verbatim: "allow" → Continue+Cancel, "block" → Cancel only.
    """
    session_key = f"duplicate_modal_{uuid.uuid4().hex[:16]}"
    request.session[session_key] = {
        "alert_title": duplicate_result.get(
            "alert_title", "Potential Duplicate Detected"
        ),
        "alert_message": str(
            duplicate_result.get(
                "alert_message",
                _("Similar records were found. Do you want to proceed?"),
            )
        ),
        "duplicate_records": [
            (r.pk, str(r)) for r in duplicate_result.get("duplicate_records", [])[:10]
        ],
        "show_duplicate_records": duplicate_result.get("show_duplicate_records", True),
        "model_name": model._meta.model_name,
        "action": rule_action,
        "save_and_new": "",
    }
    request.session.modified = True

    modal_url = reverse(
        "duplicates:duplicate_warning_modal",
        kwargs={"session_key": session_key},
    )
    return (
        f'<div hx-get="{modal_url}"'
        f' hx-target="#dynamicCreateModalBox"'
        f' hx-trigger="load"'
        f' hx-swap="innerHTML"'
        f' hx-on::load="openDynamicModal();"'
        f' style="display:none;"></div>'
    )


def _build_tab_refresh(model, pk):
    """Return an HTMX div that reloads the Potential Duplicates tab content."""
    try:
        django_content_type = HorillaContentType.objects.get_for_model(model)
        params = QueryDict(mutable=True)
        params["object_id"] = pk
        params["content_type_id"] = django_content_type.pk
        tab_url = reverse("duplicates:potential_duplicates_tab")
        return (
            f'<div hx-get="{tab_url}?{params.urlencode()}"'
            f' hx-trigger="load"'
            f' hx-target="#inner-tab-potential-duplicates-content"'
            f' hx-swap="innerHTML"'
            f' style="display:none;"></div>'
        )
    except Exception as exc:
        logging.getLogger(__name__).debug(
            "Could not build tab refresh for inline edit: %s", exc
        )
        return ""


def create_update_field_with_duplicate_check(original_post):
    """
    Wrap UpdateFieldView.post() to run duplicate checks BEFORE saving.

    Flow:
    - skip_duplicate_check=true in POST → save directly + refresh tab
    - Model/rule guards fail → save directly (no duplicate rules configured)
    - Duplicates found, action=allow → keep edit form visible + modal (Continue/Cancel)
    - Duplicates found, action=block → keep edit form visible + modal (Cancel only)
    - No duplicates → save directly + refresh tab
    """

    @wraps(original_post)
    def post_with_duplicate_check(self, request, pk, field_name, app_label, model_name):
        # User confirmed via "Continue" — save directly and refresh the tab
        if request.POST.get("skip_duplicate_check", "false").lower() == "true":
            response = original_post(
                self, request, pk, field_name, app_label, model_name
            )
            if response.status_code == 200:
                content = response.content.decode("utf-8", errors="ignore")
                if '<div id="field-' in content:
                    try:
                        model = apps.get_model(app_label, model_name)
                        return HttpResponse(content + _build_tab_refresh(model, pk))
                    except Exception:
                        pass
            return response

        # Guard: only process models registered for duplicate checking
        try:
            from horilla.registry.feature import FEATURE_REGISTRY

            model = apps.get_model(app_label, model_name)
            duplicate_models = FEATURE_REGISTRY.get("duplicate_models", [])
            if model not in duplicate_models:
                return original_post(
                    self, request, pk, field_name, app_label, model_name
                )
        except Exception:
            return original_post(self, request, pk, field_name, app_label, model_name)

        # Guard: skip duplicate check when the edited field is an owner field
        owner_fields = getattr(model, "OWNER_FIELDS", [])
        if field_name in owner_fields:
            return original_post(self, request, pk, field_name, app_label, model_name)

        # Guard: only process if model has active duplicate rules with matching rules,
        # AND the field being edited is in at least one matching rule's criteria.
        try:
            ct = HorillaContentType.objects.filter(
                model=model._meta.model_name.lower()
            ).first()
            if not ct:
                return original_post(
                    self, request, pk, field_name, app_label, model_name
                )
            rules = DuplicateRule.objects.filter(
                content_type=ct, matching_rule__isnull=False
            ).select_related("matching_rule")
            if not rules.exists():
                return original_post(
                    self, request, pk, field_name, app_label, model_name
                )
            # Only run duplicate check if the edited field is in a matching rule criterion
            field_in_criteria = rules.filter(
                matching_rule__criteria__field_name=field_name
            ).exists()
            if not field_in_criteria:
                return original_post(
                    self, request, pk, field_name, app_label, model_name
                )
        except Exception:
            return original_post(self, request, pk, field_name, app_label, model_name)

        # Build unsaved instance with the new field value applied in-memory
        try:
            obj = model.objects.get(pk=pk)
            field = next(
                (f for f in obj._meta.get_fields() if f.name == field_name), None
            )
            if not field:
                return original_post(
                    self, request, pk, field_name, app_label, model_name
                )

            if not _apply_field_value_for_check(obj, field, field_name, request):
                # Value couldn't be applied (e.g. invalid decimal) — let original handle error
                return original_post(
                    self, request, pk, field_name, app_label, model_name
                )

            duplicate_result = check_duplicates(obj, is_edit=True)

            if not duplicate_result.get("has_duplicates"):
                # No duplicates — save and refresh tab
                response = original_post(
                    self, request, pk, field_name, app_label, model_name
                )
                if response.status_code == 200:
                    content = response.content.decode("utf-8", errors="ignore")
                    if '<div id="field-' in content:
                        return HttpResponse(content + _build_tab_refresh(model, pk))
                return response

            # Duplicates found — keep edit form visible, show modal
            rule_action = duplicate_result.get("action", "allow")
            edit_form_html = _render_inline_edit_form(
                request, pk, field_name, app_label, model_name, obj, field
            )
            modal_html = _build_inline_duplicate_modal(
                request, duplicate_result, model, pk, rule_action
            )
            return HttpResponse(edit_form_html + modal_html)

        except Exception as exc:
            logging.getLogger(__name__).warning(
                "Inline edit duplicate check failed: %s", exc
            )
            return original_post(self, request, pk, field_name, app_label, model_name)

    return post_with_duplicate_check
