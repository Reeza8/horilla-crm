"""
This module contains utility functions and classes for handling permissions in the Horilla Core application.
"""

# Third-party imports (Django)
from django.contrib.auth.models import Permission
from django.db import connection, transaction

# First party imports (Horilla)
from horilla.apps import apps
from horilla.auth.models import User
from horilla.registry.permission_registry import is_permission_exempt
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
            permissions = list(
                Permission.objects.filter(
                    content_type__app_label=app_label,
                    content_type__model=model_name.lower(),
                )
            )

        by_codename = {perm.codename: perm for perm in permissions}
        model_name_lower = model_name.lower()

        simplified_permissions = []
        standard_codenames = set()
        for key in PermissionUtils.FIXED_ORDER:
            expected_codename = f"{key}_{model_name_lower}"
            standard_codenames.add(expected_codename)
            perm = by_codename.get(expected_codename)
            if perm:
                simplified_permissions.append(
                    {
                        "id": perm.id,
                        "codename": perm.codename,
                        "label": PermissionUtils.PERMISSION_MAP[key],
                    }
                )

        for perm in permissions:
            if perm.codename in standard_codenames:
                continue
            if perm.name:
                label = _(perm.name)
            else:
                label = _(perm.codename.replace("_", " ").title())

            simplified_permissions.append(
                {
                    "id": perm.id,
                    "codename": perm.codename,
                    "label": label,
                }
            )

        return simplified_permissions

    @staticmethod
    def get_all_permission_ids():
        """Return ids of all permissions of non-exempt models using a single query."""
        allowed = {
            (m._meta.app_label, m.__name__.lower())
            for m in apps.get_models()
            if not is_permission_exempt(m)
        }
        rows = Permission.objects.values_list(
            "id", "content_type__app_label", "content_type__model"
        )
        return [pid for pid, app, model in rows if (app, model) in allowed]

    @staticmethod
    def _insert_links(through, owner_model, owner_col, owner_ids, permission_ids):
        """Insert missing (owner, permission) link rows with set-based INSERT ... SELECT."""
        ops = connection.ops
        link = ops.quote_name(through._meta.db_table)
        owner_tbl = ops.quote_name(owner_model._meta.db_table)
        perm_tbl = ops.quote_name(Permission._meta.db_table)
        owner_col, perm_col = ops.quote_name(owner_col), ops.quote_name("permission_id")
        owner_ids, permission_ids = list(owner_ids), list(permission_ids)
        with transaction.atomic(), connection.cursor() as cursor:
            for i in range(0, len(owner_ids), 50):
                o_chunk = owner_ids[i : i + 50]
                for j in range(0, len(permission_ids), 500):
                    p_chunk = permission_ids[j : j + 500]
                    cursor.execute(
                        f"INSERT INTO {link} ({owner_col}, {perm_col}) "
                        f"SELECT o.id, p.id FROM {owner_tbl} o CROSS JOIN {perm_tbl} p "
                        f"WHERE o.id IN ({','.join(['%s'] * len(o_chunk))}) "
                        f"AND p.id IN ({','.join(['%s'] * len(p_chunk))}) "
                        f"AND NOT EXISTS (SELECT 1 FROM {link} x "
                        f"WHERE x.{owner_col} = o.id AND x.{perm_col} = p.id)",
                        o_chunk + p_chunk,
                    )

    @staticmethod
    def grant_permissions_to_users(user_ids, permission_ids):
        """Grant permissions to users in bulk, skipping existing rows."""
        PermissionUtils._insert_links(
            User.user_permissions.through,
            User,
            "horillauser_id",
            user_ids,
            permission_ids,
        )

    @staticmethod
    def grant_permissions_to_role(role, permission_ids):
        """Grant permissions to a role in bulk, skipping existing rows."""
        PermissionUtils._insert_links(
            role.permissions.through, type(role), "role_id", [role.pk], permission_ids
        )

    @staticmethod
    def _delete_links(through, owner_col, owner_ids, permission_ids):
        """Delete (owner, permission) link rows with raw chunked DELETE statements."""
        ops = connection.ops
        link = ops.quote_name(through._meta.db_table)
        owner_col, perm_col = ops.quote_name(owner_col), ops.quote_name("permission_id")
        owner_ids, permission_ids = list(owner_ids), list(permission_ids)
        with transaction.atomic(), connection.cursor() as cursor:
            for i in range(0, len(owner_ids), 50):
                o_chunk = owner_ids[i : i + 50]
                for j in range(0, len(permission_ids), 500):
                    p_chunk = permission_ids[j : j + 500]
                    cursor.execute(
                        f"DELETE FROM {link} "
                        f"WHERE {owner_col} IN ({','.join(['%s'] * len(o_chunk))}) "
                        f"AND {perm_col} IN ({','.join(['%s'] * len(p_chunk))})",
                        o_chunk + p_chunk,
                    )

    @staticmethod
    def revoke_permissions_from_users(user_ids, permission_ids):
        """Revoke permissions from users with raw bulk deletes."""
        PermissionUtils._delete_links(
            User.user_permissions.through, "horillauser_id", user_ids, permission_ids
        )

    @staticmethod
    def revoke_permissions_from_role(role, permission_ids):
        """Revoke permissions from a role with a raw bulk delete."""
        PermissionUtils._delete_links(
            role.permissions.through, "role_id", [role.pk], permission_ids
        )

    @staticmethod
    def all_models_selected(all_models):
        """Return True when every listed model has all its permissions granted."""
        return bool(all_models) and all(m.get("select_all_checked") for m in all_models)

    @staticmethod
    def get_all_models_data(user=None, role=None, search_query=None):
        """Retrieve all models with their permissions, optionally checking user or role permissions."""

        all_permissions = list(Permission.objects.select_related("content_type").all())
        permissions_by_model = {}
        for perm in all_permissions:
            key = (perm.content_type.app_label, perm.content_type.model)
            permissions_by_model.setdefault(key, []).append(perm)

        granted_ids = None
        if user is not None:
            granted_ids = set(user.user_permissions.values_list("id", flat=True))
        elif role is not None:
            granted_ids = set(role.permissions.values_list("id", flat=True))

        all_models = []
        for model in apps.get_models():
            model_name = model.__name__
            app_label = model._meta.app_label

            if is_permission_exempt(model):
                continue

            if search_query:
                verbose_name = model._meta.verbose_name.lower()
                verbose_name_plural = model._meta.verbose_name_plural.lower()
                search_lower = search_query.lower()

                if not (
                    search_lower in verbose_name
                    or search_lower in verbose_name_plural
                    or search_lower in model_name.lower()
                    or search_lower in app_label.lower()
                ):
                    continue

            model_permissions = permissions_by_model.get(
                (app_label, model_name.lower()), []
            )
            permissions = PermissionUtils.get_model_permissions(
                app_label, model_name, permissions=model_permissions
            )
            if permissions:
                has_export = any(
                    perm["codename"] == f"export_{model_name.lower()}"
                    for perm in permissions
                )
                model_data = {
                    "app_label": app_label,
                    "model_name": model_name,
                    "verbose_name": model._meta.verbose_name,
                    "verbose_name_plural": model._meta.verbose_name_plural,
                    "permissions": permissions,
                    "is_managed": model._meta.managed,
                    "has_export": has_export,
                }
                if granted_ids is not None:
                    all_permissions_checked = True
                    has_any_permission = False
                    for perm in permissions:
                        has_perm = perm["id"] in granted_ids
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
