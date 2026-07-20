"""
This module contains utility functions and classes for handling permissions in the Horilla Core application.
"""

# Third-party imports (Django)
from django.contrib.auth.models import Permission

# First party imports (Horilla)
from horilla.apps import apps
from horilla.registry.permission_registry import PERMISSION_EXEMPT_MODELS
from horilla.utils.translation import gettext_lazy as _


class PermissionUtils:
    """Utility class to handle common permission-related logic."""

    FIXED_ORDER = [
        "add",
        "change",
        "view",
        "delete",
        "export",
        "add_own",
        "change_own",
        "view_own",
        "delete_own",
        "export_own",
    ]

    PERMISSION_MAP = {
        "add": _("Create"),
        "change": _("Change"),
        "view": _("View"),
        "delete": _("Delete"),
        "export": _("Export"),
        "add_own": _("Create Own"),
        "change_own": _("Change Own"),
        "view_own": _("View Own"),
        "delete_own": _("Delete Own"),
        "export_own": _("Export Own"),
    }

    @staticmethod
    def get_model_permissions(app_label, model_name, permissions=None):
        """Retrieve permissions for a specific model."""
        if permissions is None:
            permissions = Permission.objects.filter(
                content_type__app_label=app_label,
                content_type__model=model_name.lower(),
            )
        simplified_permissions = []
        for key in PermissionUtils.FIXED_ORDER:
            expected_codename = f"{key}_{model_name.lower()}"
            perm = permissions.filter(codename=expected_codename).first()
            if perm:
                simplified_permissions.append(
                    {
                        "id": perm.id,
                        "codename": perm.codename,
                        "label": PermissionUtils.PERMISSION_MAP[key],
                    }
                )

        standard_codenames = [
            f"{key}_{model_name.lower()}" for key in PermissionUtils.FIXED_ORDER
        ]
        custom_permissions = permissions.exclude(codename__in=standard_codenames)

        for perm in custom_permissions:
            label = perm.name if perm.name else perm.codename.replace("_", " ").title()

            simplified_permissions.append(
                {
                    "id": perm.id,
                    "codename": perm.codename,
                    "label": label,
                }
            )

        return simplified_permissions

    @staticmethod
    def get_all_models_data(user=None, role=None, search_query=None):
        """Retrieve all models with their permissions, optionally checking user or role permissions."""

        all_models = []
        for model in apps.get_models():
            model_name = model.__name__
            app_label = model._meta.app_label

            if model_name in PERMISSION_EXEMPT_MODELS:
                continue

            if search_query:
                verbose_name = model._meta.verbose_name.title().lower()
                verbose_name_plural = model._meta.verbose_name_plural.title().lower()
                search_lower = search_query.lower()

                if not (
                    search_lower in verbose_name
                    or search_lower in verbose_name_plural
                    or search_lower in model_name.lower()
                    or search_lower in app_label.lower()
                ):
                    continue

            permissions = PermissionUtils.get_model_permissions(app_label, model_name)
            if permissions:
                has_export = any(
                    perm["codename"] == f"export_{model_name.lower()}"
                    for perm in permissions
                )
                model_data = {
                    "app_label": app_label,
                    "model_name": model_name,
                    "verbose_name": model._meta.verbose_name.title(),
                    "verbose_name_plural": model._meta.verbose_name_plural.title(),
                    "permissions": permissions,
                    "is_managed": model._meta.managed,
                    "has_export": has_export,
                }
                if user or role:
                    all_permissions_checked = True
                    has_any_permission = False
                    for perm in permissions:
                        has_perm = (
                            user.user_permissions.filter(id=perm["id"]).exists()
                            if user
                            else role.permissions.filter(id=perm["id"]).exists()
                        )
                        perm["has_perm"] = has_perm
                        if has_perm:
                            has_any_permission = True
                        else:
                            all_permissions_checked = False
                    model_data["select_all_checked"] = (
                        all_permissions_checked
                        and has_any_permission
                        and len(permissions) > 0
                    )
                all_models.append(model_data)
        return sorted(
            all_models,
            key=lambda m: (
                m["is_managed"],
                not m["has_export"],
                m["app_label"],
                m["model_name"],
            ),
        )
