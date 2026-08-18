"""Recipient and field selection views (add/remove email, suggestions, field selection)."""

# Standard library imports
import logging

# Third-party imports (Django)
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View

# First party imports (Horilla)
from horilla.apps import apps
from horilla.contrib.core.methods import get_template_reverse_models
from horilla.contrib.core.models import HorillaContentType
from horilla.shortcuts import render
from horilla.utils.decorators import (
    htmx_required,
    method_decorator,
    permission_required_or_denied,
)
from horilla.utils.translation import gettext as _
from horilla.views.generic import TemplateView

# Local imports
from ...models import HorillaMail

logger = logging.getLogger(__name__)


@method_decorator(
    permission_required_or_denied(
        [
            "mail.change_horillamail",
            "mail.change_own_horillamail",
        ]
    ),
    name="dispatch",
)
class AddEmailView(LoginRequiredMixin, View):
    """
    View to add email as a pill and clear search input
    """

    def post(self, request, *args, **kwargs):
        """
        Add email to the pill list
        """
        email = request.POST.get("email", "").strip()
        field_type = request.POST.get("field_type", "to")
        current_email_list = request.POST.get(f"{field_type}_email_list", "")

        if current_email_list:
            email_list = [e.strip() for e in current_email_list.split(",") if e.strip()]
        else:
            email_list = []

        if email and email not in email_list:
            email_list.append(email)

        email_string = ", ".join(email_list)

        context = {
            "email_list": email_list,
            "email_string": email_string,
            "field_type": field_type,
            "current_search": "",
        }

        return render(request, "email_pills_field.html", context)


@method_decorator(
    permission_required_or_denied(
        [
            "mail.change_horillamail",
            "mail.change_own_horillamail",
        ]
    ),
    name="dispatch",
)
class RemoveEmailView(LoginRequiredMixin, View):
    """
    View to remove specific email pill
    """

    def post(self, request, *args, **kwargs):
        """
        Remove email from the pill list
        """
        email_to_remove = request.POST.get("email_to_remove", "").strip()
        field_type = request.POST.get("field_type", "to")
        current_email_list = request.POST.get(f"{field_type}_email_list", "")

        if current_email_list:
            email_list = [e.strip() for e in current_email_list.split(",") if e.strip()]
        else:
            email_list = []

        if email_to_remove in email_list:
            email_list.remove(email_to_remove)

        email_string = ", ".join(email_list)

        context = {
            "email_list": email_list,
            "email_string": email_string,
            "field_type": field_type,
            "current_search": "",
        }

        return render(request, "email_pills_field.html", context)


@method_decorator(htmx_required, name="dispatch")
@method_decorator(
    permission_required_or_denied(
        [
            "mail.view_horillamail",
            "mail.view_own_horillamail",
        ]
    ),
    name="dispatch",
)
class EmailSuggestionView(LoginRequiredMixin, View):
    """
    View to get email suggestions (updated to work with pills)
    """

    def get_all_emails_from_models(self):
        """
        Extract all email addresses from all models in the project
        """
        all_emails = set()

        for model in apps.get_models():
            model_name = model._meta.model_name.lower()
            if model_name in [
                "session",
                "contenttype",
                "permission",
                "group",
                "logentry",
            ]:
                continue

            for field in model._meta.get_fields():
                if (
                    "email" in field.name.lower()
                    or field.__class__.__name__ == "EmailField"
                ):
                    try:
                        values = model.objects.values_list(
                            field.name, flat=True
                        ).distinct()
                        for value in values:
                            if value and "@" in str(value):
                                self._extract_emails_from_string(str(value), all_emails)
                    except Exception:
                        continue

        try:
            for field_name in ["to", "cc", "bcc"]:
                try:
                    email_values = HorillaMail.objects.values_list(
                        field_name, flat=True
                    ).distinct()
                    for email_string in email_values:
                        if email_string:
                            self._extract_emails_from_string(email_string, all_emails)
                except Exception:
                    continue

        except ImportError:
            pass

        valid_emails = []
        for email in all_emails:
            if self._is_valid_email(email):
                valid_emails.append(email.lower())

        return sorted(list(set(valid_emails)))

    def _extract_emails_from_string(self, email_string, email_set):
        """
        Extract individual emails from a string that might contain multiple emails
        """
        if "," in email_string:
            emails = [email.strip() for email in email_string.split(",")]
            email_set.update(emails)
        elif ";" in email_string:
            emails = [email.strip() for email in email_string.split(";")]
            email_set.update(emails)
        else:
            email_set.add(email_string.strip())

    def _is_valid_email(self, email):
        """
        Basic email validation
        """
        if not email or len(email) < 5:
            return False
        if "@" not in email:
            return False
        parts = email.split("@")
        if len(parts) != 2:
            return False
        if "." not in parts[1]:
            return False
        return True

    def get(self, request, *args, **kwargs):
        """
        Return email suggestions based on search query
        """
        field_type = request.GET.get("field", "to")
        current_input = request.GET.get(f"{field_type}_email_input", "").strip()
        current_email_list = request.GET.get(f"{field_type}_email_list", "")

        existing_emails = []
        if current_email_list:
            existing_emails = [
                e.strip().lower() for e in current_email_list.split(",") if e.strip()
            ]

        all_emails = self.get_all_emails_from_models()

        available_emails = [
            email for email in all_emails if email.lower() not in existing_emails
        ]

        if current_input:
            search_lower = current_input.lower()
            filtered_emails = [
                email for email in available_emails if search_lower in email.lower()
            ]
            exact_matches = [e for e in filtered_emails if e.lower() == search_lower]
            starts_with = [
                e
                for e in filtered_emails
                if e.lower().startswith(search_lower) and e not in exact_matches
            ]
            contains = [
                e
                for e in filtered_emails
                if search_lower in e.lower()
                and e not in exact_matches
                and e not in starts_with
            ]

            filtered_emails = exact_matches + starts_with + contains
        else:
            filtered_emails = available_emails[:10]

        filtered_emails = filtered_emails[:15]

        context = {
            "emails": filtered_emails,
            "field_type": field_type,
            "query": current_input,
        }

        return render(request, "email_suggestions.html", context)


@method_decorator(htmx_required, name="dispatch")
@method_decorator(
    permission_required_or_denied(
        [
            "mail.view_horillamail",
            "mail.view_own_horillamail",
        ]
    ),
    name="dispatch",
)
class HorillaMailFieldSelectionView(LoginRequiredMixin, TemplateView):
    """
    View to show all fields of the related model for insertion into email templates
    """

    template_name = "field_selection_modal.html"

    def get_context_data(self, **kwargs):
        """Build context with model/instance fields for template variable insertion."""
        context = super().get_context_data(**kwargs)

        model_name = self.request.GET.get("model_name")
        object_id = self.request.GET.get("object_id")
        content_type_id = self.request.GET.get("content_type")

        if model_name or content_type_id:
            tab_type = self.request.GET.get(
                "tab_type", "instance"
            )  # Default to instance if model exists
        else:
            tab_type = self.request.GET.get(
                "tab_type", "user"
            )  # Default to user if no model

        excluded_fields = {
            "is_active",
            "additional_info",
            "history",
            "password",
            "user_permissions",
            "groups",
            "last_login",
            "date_joined",
            "is_staff",
            "is_superuser",
            "recycle_bin_policy",
        }

        try:
            if tab_type == "instance" and model_name or content_type_id:
                if model_name:
                    content_type = HorillaContentType.objects.get(
                        model=model_name.lower()
                    )
                else:
                    content_type = HorillaContentType.objects.get(id=content_type_id)
                    # Use content_type.model (e.g. 'employee') for URLs, not verbose_name,
                    # so tab links send a value that HorillaContentType.objects.get(model=...) can find
                    model_name = content_type.model
                model_class = apps.get_model(
                    app_label=content_type.app_label, model_name=content_type.model
                )
                related_object = None
                if object_id and object_id != "None":
                    related_object = model_class.objects.get(pk=object_id)

                model_fields = []

                # Get regular fields (skip editable=False)
                for field in model_class._meta.get_fields():
                    if field.name in excluded_fields:
                        continue
                    if not getattr(field, "editable", True):
                        continue

                    if not field.many_to_many and not field.one_to_many:
                        field_info = {
                            "name": field.name,
                            "verbose_name": getattr(field, "verbose_name", field.name),
                            "field_type": field.__class__.__name__,
                            "template_syntax": f"{{{{ instance.{field.name} }}}}",
                            "is_foreign_key": (
                                field.many_to_one
                                if hasattr(field, "many_to_one")
                                else False
                            ),
                            "is_relation": hasattr(field, "related_model"),
                        }

                        model_fields.append(field_info)

                foreign_key_fields = []
                for field in model_class._meta.get_fields():
                    # Skip excluded fields
                    if field.name in excluded_fields:
                        continue
                    if not getattr(field, "editable", True):
                        continue

                    if field.many_to_one and hasattr(field, "related_model"):
                        # Get fields from the related model without needing object instance
                        for related_field in field.related_model._meta.get_fields():
                            # Skip excluded fields in related model too
                            if related_field.name in excluded_fields:
                                continue
                            if not getattr(related_field, "editable", True):
                                continue

                            if (
                                not related_field.many_to_many
                                and not related_field.one_to_many
                            ):
                                fk_field_info = {
                                    "name": (f"{field.name}.{related_field.name}"),
                                    "verbose_name": (
                                        getattr(
                                            related_field,
                                            "verbose_name",
                                            related_field.name,
                                        )
                                    ),
                                    "header": field.verbose_name,
                                    "field_type": (
                                        f"{field.__class__.__name__} -> "
                                        f"{related_field.__class__.__name__}"
                                    ),
                                    "template_syntax": (
                                        f"{{{{ instance.{field.name}."
                                        f"{related_field.name} }}}}"
                                    ),
                                    "parent_field": field.name,
                                    "is_foreign_key": True,
                                }

                                foreign_key_fields.append(fk_field_info)

                reverse_relation_fields = []

                # Models allowed as reverse relations in Insert field (feature registry)
                allowed_reverse_models = get_template_reverse_models()

                # Models already shown in Related Fields (forward FKs) - don't show again in Reverse
                related_models_in_forward = set()
                for f in model_class._meta.get_fields():
                    if (
                        f.many_to_one
                        and hasattr(f, "related_model")
                        and f.related_model
                    ):
                        related_models_in_forward.add(f.related_model)

                # Get all reverse relations
                for field in model_class._meta.get_fields():
                    if field.one_to_many or field.many_to_many:
                        # Skip fields that don't have get_accessor_name method
                        # (e.g., AuditlogHistoryField)
                        if not hasattr(field, "get_accessor_name"):
                            continue
                        try:
                            # Get the accessor name (like 'employee_set' or custom related_name)
                            accessor_name = field.get_accessor_name()

                            related_model = field.related_model

                            # Skip reverse relation if this model is already in Related Fields
                            if (
                                related_model
                                and related_model in related_models_in_forward
                            ):
                                continue

                            # Include only models in template_reverse registry when feature is registered
                            if (
                                allowed_reverse_models is not None
                                and related_model not in allowed_reverse_models
                            ):
                                continue

                            if related_model:
                                for reverse_field in related_model._meta.get_fields():
                                    if (
                                        reverse_field.name in excluded_fields
                                        or reverse_field.many_to_many
                                        or reverse_field.one_to_many
                                    ):
                                        continue
                                    if not getattr(reverse_field, "editable", True):
                                        continue

                                    if (
                                        hasattr(reverse_field, "related_model")
                                        and reverse_field.related_model == model_class
                                    ):
                                        continue

                                    reverse_field_info = {
                                        "name": (
                                            f"{accessor_name}.first."
                                            f"{reverse_field.name}"
                                        ),
                                        "verbose_name": (
                                            getattr(
                                                reverse_field,
                                                "verbose_name",
                                                reverse_field.name,
                                            )
                                        ),
                                        "header": field.related_model._meta.verbose_name,
                                        "field_type": (
                                            f"Reverse {field.__class__.__name__} -> "
                                            f"{reverse_field.__class__.__name__}"
                                        ),
                                        "template_syntax": (
                                            f"{{{{ instance.{accessor_name}|join_attr:"
                                            f"'{reverse_field.name}' }}}}"
                                        ),
                                        "parent_field": accessor_name,
                                        "is_reverse_relation": True,
                                    }

                                    reverse_relation_fields.append(reverse_field_info)
                        except Exception as e:
                            logger.error(
                                "Error processing reverse relation splits: %s",
                                e,
                            )
                            continue

                context["model_fields"] = model_fields
                context["foreign_key_fields"] = foreign_key_fields
                context["reverse_relation_fields"] = reverse_relation_fields
                context["related_object"] = related_object

            elif tab_type == "user":
                user = self.request.user
                model_fields = []

                for field in user._meta.get_fields():
                    if field.name in excluded_fields:
                        continue
                    if not getattr(field, "editable", True):
                        continue

                    if not field.many_to_many and not field.one_to_many:
                        field_info = {
                            "name": field.name,
                            "verbose_name": getattr(field, "verbose_name", field.name),
                            "field_type": field.__class__.__name__,
                            "template_syntax": f"{{{{ request.user.{field.name} }}}}",
                            "is_foreign_key": (
                                field.many_to_one
                                if hasattr(field, "many_to_one")
                                else False
                            ),
                            "is_relation": hasattr(field, "related_model"),
                        }

                        model_fields.append(field_info)

                context["model_fields"] = model_fields
                context["foreign_key_fields"] = []
                context["reverse_relation_fields"] = []
                context["related_object"] = user

            elif tab_type == "company":
                # Get current active company fields
                company = getattr(self.request, "active_company", None)

                if company:
                    model_fields = []

                    for field in company._meta.get_fields():
                        if field.name in excluded_fields:
                            continue
                        if not getattr(field, "editable", True):
                            continue

                        if not field.many_to_many and not field.one_to_many:
                            field_info = {
                                "name": field.name,
                                "verbose_name": getattr(
                                    field, "verbose_name", field.name
                                ),
                                "field_type": field.__class__.__name__,
                                "template_syntax": f"{{{{ request.active_company.{field.name} }}}}",
                                "is_foreign_key": (
                                    field.many_to_one
                                    if hasattr(field, "many_to_one")
                                    else False
                                ),
                                "is_relation": hasattr(field, "related_model"),
                            }

                            model_fields.append(field_info)

                    context["model_fields"] = model_fields
                    context["foreign_key_fields"] = []
                    context["reverse_relation_fields"] = []
                    context["related_object"] = company
                else:
                    context["error"] = "No active company found"

            elif tab_type == "request":
                # Get request object fields (commonly used request attributes)
                request_fields = [
                    {
                        "name": "get_host",
                        "verbose_name": "Host",
                        "template_syntax": "{{ request.get_host }}",
                    },
                    {
                        "name": "scheme",
                        "verbose_name": "Scheme",
                        "template_syntax": "{{ request.scheme }}",
                    },
                ]

                model_fields = []
                for field_data in request_fields:
                    field_info = {
                        "name": field_data["name"],
                        "verbose_name": field_data["verbose_name"],
                        "field_type": "RequestAttribute",
                        "template_syntax": field_data["template_syntax"],
                        "is_foreign_key": False,
                        "is_relation": False,
                    }

                    model_fields.append(field_info)

                context["model_fields"] = model_fields
                context["foreign_key_fields"] = []
                context["reverse_relation_fields"] = []
                context["related_object"] = self.request

            context["has_model_name"] = bool(model_name) or bool(content_type_id)
            context["model_name"] = model_name
            context["object_id"] = object_id
            context["tab_type"] = tab_type

        except Exception as e:
            context["error"] = f"Error loading fields: {str(e)}"
        return context
