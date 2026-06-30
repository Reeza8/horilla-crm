"""
This module contains signal handlers and utility functions for Horilla's core
models such as Company, FiscalYear, MultipleCurrency, and related
models.
"""

# Standard library imports
import logging
import threading
from decimal import Decimal

from django.contrib.auth.models import Permission
from django.core.cache import cache

# Third-party imports (Django)
from django.dispatch import Signal, receiver
from django.utils.encoding import force_str

from horilla.apps import apps
from horilla.auth.models import User
from horilla.contrib.utils.middlewares import _thread_local

# First party imports (Horilla)
from horilla.db import transaction
from horilla.db.models import Q
from horilla.db.models.signals import post_delete, post_migrate, post_save, pre_save
from horilla.utils import timezone

from .models import (
    Company,
    DetailFieldVisibility,
    FieldPermission,
    FiscalYear,
    HorillaContentType,
    ListColumnVisibility,
    MultipleCurrency,
    Role,
)
from .services.fiscal_year_service import FiscalYearService

# Local imports
from .utils import fetch_exchange_rates_bulk, get_user_field_permission

logger = logging.getLogger(__name__)


# Fired after a company default currency changes; listeners bulk-update MoneyField amounts.
company_currency_changed = Signal()
# Fired when a new Company is created; listeners initialize fiscal year, currency, etc.
company_created = Signal()
pre_logout_signal = Signal()
pre_login_render_signal = Signal()


def handle_company_currency_change(company, old_currency):
    """
    Handle currency change with optimized bulk updates and correct conversion logic.
    Kept in signals so Company model does not need to import MultipleCurrency.
    Updates conversion rates for all non-default currencies using a single bulk
    API call; falls back to ratio math if fetch fails.
    ``company_currency_changed`` is sent in a background thread so listener bulk
    updates do not block the response.
    """
    request = getattr(_thread_local, "request", None)
    try:
        with transaction.atomic():
            old_default = MultipleCurrency.all_objects.filter(
                company=company, currency=old_currency
            ).first()

            new_default_currency = MultipleCurrency.all_objects.filter(
                company=company, currency=company.currency
            ).first()

            if not new_default_currency:
                new_default_currency = MultipleCurrency.all_objects.create(
                    company=company,
                    currency=company.currency,
                    is_default=True,
                    conversion_rate=Decimal("1.00"),
                    decimal_places=2,
                    format="western_format",
                    created_at=timezone.now(),
                    updated_at=timezone.now(),
                    created_by=request.user if request else None,
                    updated_by=request.user if request else None,
                )

            original_new_default_rate = new_default_currency.conversion_rate or Decimal(
                "1.0"
            )
            MultipleCurrency.all_objects.filter(company=company).update(
                is_default=False
            )
            new_default_currency.is_default = True
            new_default_currency.conversion_rate = Decimal("1.00")
            new_default_currency.save()

            base_code = new_default_currency.currency
            other_currencies = list(
                MultipleCurrency.all_objects.filter(company=company).exclude(
                    pk=new_default_currency.pk
                )
            )

            # Single bulk API call instead of one per currency
            target_codes = [c.currency for c in other_currencies]
            bulk_rates = fetch_exchange_rates_bulk(base_code, target_codes)

            currencies_to_update = []
            for curr in other_currencies:
                rate = bulk_rates.get(curr.currency)
                if rate is not None:
                    curr.conversion_rate = rate
                else:
                    current_rate = curr.conversion_rate or Decimal("1.0")
                    curr.conversion_rate = current_rate / original_new_default_rate
                currencies_to_update.append(curr)

            if currencies_to_update:
                MultipleCurrency.all_objects.bulk_update(
                    currencies_to_update, ["conversion_rate"]
                )

            old_rate = old_default.conversion_rate if old_default else Decimal("1.0")
            conversion_rate = Decimal("1.0") / old_rate

        # Send signal in a background thread so listener bulk updates don't block the response
        def _send_currency_changed():
            try:
                company_currency_changed.send(
                    sender=Company, company=company, conversion_rate=conversion_rate
                )
            except Exception as exc:
                logger.error(
                    "Background currency change update failed for company %s: %s",
                    company.id,
                    exc,
                )

        threading.Thread(target=_send_currency_changed, daemon=True).start()

    except Exception as e:
        logger.error(
            "Error handling currency change for company %s: %s",
            company.id,
            e,
        )
        raise


@receiver(pre_save, sender=Company)
def _mark_company_currency_change_pending(sender, instance, **kwargs):
    """
    On update, if currency changed, store old currency so post_save can run
    handle_company_currency_change without Company importing from signals.
    """
    if instance.pk and instance.currency is not None:
        old = getattr(instance, "_original_currency", None)
        if old is not None and old != instance.currency:
            instance._pending_currency_change = old


@receiver(post_save, sender=Company)
def _handle_pending_company_currency_change(sender, instance, created, **kwargs):
    """Run currency-change logic when currency was changed (no import in Company)."""
    old = getattr(instance, "_pending_currency_change", None)
    if created or old is None:
        return
    try:
        handle_company_currency_change(instance, old)
    finally:
        if hasattr(instance, "_pending_currency_change"):
            del instance._pending_currency_change


@receiver(post_save, sender="core.Company")
def create_company_fiscal_config(sender, instance, created, **kwargs):
    """
    Handle fiscal year configuration when a company is created
    """
    if created:
        try:
            config = FiscalYear.objects.get(company=instance)
        except FiscalYear.DoesNotExist:
            config = FiscalYearService.get_or_create_company_configuration(instance)

        FiscalYearService.generate_fiscal_years(config)


@receiver(post_save, sender="core.FiscalYear")
def generate_fiscal_years_on_config_save(sender, instance, created, **kwargs):
    """
    Generate fiscal years when configuration is saved.
    Uses transaction.on_commit to avoid database locking issues.
    """
    if not created and instance.company:  # Only run on updates, not creation
        transaction.on_commit(lambda: FiscalYearService.generate_fiscal_years(instance))


@receiver(post_save, sender=Company)
def create_default_currency(sender, instance, created, **kwargs):
    """
    Create default currency for new companies and update conversion rates.
    """
    if created and instance.currency:
        try:
            with transaction.atomic():
                if not MultipleCurrency.all_objects.filter(
                    company=instance, currency=instance.currency
                ).exists():
                    new_currency = MultipleCurrency.all_objects.create(
                        company=instance,
                        currency=instance.currency,
                        is_default=True,
                        conversion_rate=Decimal("1.00"),
                        decimal_places=2,
                        format="western_format",
                        created_by=instance.created_by,
                        updated_by=instance.updated_by,
                    )
                    all_currencies = MultipleCurrency.all_objects.filter(
                        company=instance
                    ).exclude(pk=new_currency.pk)
                    if all_currencies.exists():
                        for curr in all_currencies:
                            curr.is_default = False
                            curr.save()
        except Exception as e:
            logger.error(
                "Error creating default currency for company %s: %s",
                instance.id,
                e,
            )


@receiver(post_save, sender=Company)
def sync_default_currency_when_multiple_off(sender, instance, created, **kwargs):
    """
    When multiple currencies are OFF, keep the default MultipleCurrency in sync
    with company.currency so that the default changes when the user changes
    company currency (and when they turn multi-currency back on, default is correct).
    """
    if getattr(instance, "activate_multiple_currencies", False):
        return
    if not instance.currency:
        return
    try:
        with transaction.atomic():
            _default_currency = MultipleCurrency.all_objects.filter(
                company=instance, is_default=True
            ).first()

            matching = MultipleCurrency.all_objects.filter(
                company=instance, currency=instance.currency
            ).first()

            if not matching:
                request = getattr(_thread_local, "request", None)
                matching = MultipleCurrency.all_objects.create(
                    company=instance,
                    currency=instance.currency,
                    is_default=True,
                    conversion_rate=Decimal("1.00"),
                    decimal_places=2,
                    format="western_format",
                    created_by=request.user if request else None,
                    updated_by=request.user if request else None,
                )
            else:
                MultipleCurrency.all_objects.filter(company=instance).update(
                    is_default=False
                )
                matching.is_default = True
                matching.conversion_rate = Decimal("1.00")
                matching.save()
            MultipleCurrency.all_objects.filter(company=instance).exclude(
                pk=matching.pk
            ).delete()

    except Exception as e:
        logger.error(
            "Error syncing default currency when multi-currency off for company %s: %s",
            instance.pk,
            e,
        )


@receiver(post_save, sender=Company)
def sync_company_currency_to_default_multiple(sender, instance, created, **kwargs):
    """
    When multiple currencies are active, keep company.currency in sync with
    the default MultipleCurrency. Runs after save so that default-currency
    logic is handled via signals instead of inside Company.save().
    """
    if not getattr(instance, "activate_multiple_currencies", False):
        return
    default_currency = MultipleCurrency.all_objects.filter(
        company=instance, is_default=True
    ).first()
    if not default_currency or default_currency.currency == instance.currency:
        return
    try:
        old_currency = instance.currency
        instance.currency = default_currency.currency
        handle_company_currency_change(instance, old_currency)
    except Exception as e:
        logger.error(
            "Error syncing company %s currency to default multiple: %s",
            instance.pk,
            e,
        )
        raise
    Company.objects.filter(pk=instance.pk).update(currency=instance.currency)


def add_custom_permissions(sender, **kwargs):
    """
    Add custom permissions for models
    that define default Django permissions.
    """
    for model in apps.get_models():
        opts = model._meta

        # Skip models that don't use default permissions
        if opts.default_permissions == ():
            continue

        content_type = HorillaContentType.objects.get_for_model(model)

        add_view_own = (
            "view_own" in opts.default_permissions
            or opts.default_permissions == ("add", "change", "delete", "view")
        )

        add_change_own = (
            "change_own" in opts.default_permissions
            or opts.default_permissions == ("add", "change", "delete", "view")
        )

        add_create_own = (
            "create_own" in opts.default_permissions
            or opts.default_permissions == ("add", "change", "delete", "view")
        )

        add_delete_own = (
            "delete_own" in opts.default_permissions
            or opts.default_permissions == ("add", "change", "delete", "view")
        )

        custom_perms = []

        if add_view_own:
            custom_perms.append(("view_own", f"Can view own {opts.verbose_name_raw}"))

        if add_change_own:
            custom_perms.append(
                ("change_own", f"Can change own {opts.verbose_name_raw}")
            )

        if add_create_own:
            custom_perms.append(("add_own", f"Can create own {opts.verbose_name_raw}"))

        if add_delete_own:
            custom_perms.append(
                ("delete_own", f"Can delete own {opts.verbose_name_raw}")
            )

        for code_prefix, name in custom_perms:
            codename = f"{code_prefix}_{opts.model_name}"
            if not Permission.objects.filter(
                codename=codename, content_type=content_type
            ).exists():
                Permission.objects.create(
                    codename=codename,
                    name=name,
                    content_type=content_type,
                )


post_migrate.connect(add_custom_permissions)


@receiver(pre_save, sender=User)
def capture_user_old_role(sender, instance, **kwargs):
    """Store the previous role on the instance so post_save can detect role changes."""
    if instance.pk:
        try:
            instance._previous_role = User.objects.get(pk=instance.pk).role
        except User.DoesNotExist:
            instance._previous_role = None
    else:
        instance._previous_role = None


@receiver(post_save, sender=User)
def sync_role_permissions_on_role_change(sender, instance, created, **kwargs):
    """
    When a user's role changes (via any code path), sync user_permissions:
    - Remove permissions that came from the old role (excluding view_own defaults).
    - Add all permissions from the new role.
    For newly created users with a role, add all role permissions immediately.
    """
    new_role = instance.role

    if created:
        if new_role is None:
            return

        def assign_role_permissions_on_create():
            try:
                role_perms = list(new_role.permissions.all())
                if role_perms:
                    instance.user_permissions.add(*role_perms)
            except Exception as e:
                logger.error(
                    "Error assigning role permissions for new user %s: %s",
                    instance.pk,
                    e,
                )

        transaction.on_commit(assign_role_permissions_on_create)
        return

    old_role = getattr(instance, "_previous_role", None)

    if old_role == new_role:
        return

    def sync_permissions():
        try:
            view_own_perm_ids = set(
                Permission.objects.filter(codename__startswith="view_own_").values_list(
                    "id", flat=True
                )
            )

            if old_role is not None:
                old_role_perm_ids = set(
                    old_role.permissions.values_list("id", flat=True)
                )
                to_remove_ids = old_role_perm_ids - view_own_perm_ids
                if to_remove_ids:
                    perms_to_remove = Permission.objects.filter(id__in=to_remove_ids)
                    instance.user_permissions.remove(*perms_to_remove)

            if new_role is not None:
                new_role_perms = list(new_role.permissions.all())
                if new_role_perms:
                    instance.user_permissions.add(*new_role_perms)

        except Exception as e:
            logger.error(
                "Error syncing permissions for user %s on role change: %s",
                instance.pk,
                e,
            )

    transaction.on_commit(sync_permissions)


@receiver(post_save, sender=User)
def ensure_view_own_permissions(sender, instance, created, **kwargs):
    """
    Assign view_own permissions to newly created non-superuser users.
    """
    if not created or instance.is_superuser:
        return

    def assign_permissions():
        try:
            view_own_perms = Permission.objects.filter(codename__startswith="view_own_")
            if view_own_perms.exists():
                instance.user_permissions.add(*view_own_perms)
        except Exception as e:
            print(f"✗ Error assigning permissions to {instance.username}: {e}")

    transaction.on_commit(assign_permissions)


@receiver(post_save, sender=Role)
def ensure_role_view_own_permissions(sender, instance, created, **kwargs):
    """
    Assign view_own permissions to newly created or updated roles.
    Also assign these permissions to all members of the role.
    """

    def assign_permissions():
        try:
            view_own_perms = Permission.objects.filter(codename__startswith="view_own_")

            if not view_own_perms.exists():
                print(f"✗ No view_own permissions found")
                return

            existing_perm_ids = set(instance.permissions.values_list("id", flat=True))

            view_own_perm_ids = set(view_own_perms.values_list("id", flat=True))

            missing_perm_ids = view_own_perm_ids - existing_perm_ids

            if missing_perm_ids:
                missing_perms = Permission.objects.filter(id__in=missing_perm_ids)

                instance.permissions.add(*missing_perms)

                members = instance.users.all()
                for member in members:
                    member.user_permissions.add(*missing_perms)

                if created:
                    print(
                        f"✓ Assigned {len(missing_perm_ids)} view_own permissions to new role '{instance.role_name}'"
                    )
                else:
                    print(
                        f"✓ Updated {len(missing_perm_ids)} view_own permissions for role '{instance.role_name}'"
                    )

                if members.exists():
                    print(
                        f"  ✓ Updated {members.count()} members of role '{instance.role_name}'"
                    )

        except Exception as e:
            print(f"✗ Error assigning permissions to role '{instance.role_name}': {e}")

    transaction.on_commit(assign_permissions)


@receiver(post_save, sender=User)
def user_default_field_permissions(sender, instance, created, **kwargs):
    """
    Assign default field permissions to newly created users.
    """
    if not created or instance.is_superuser:
        return

    def assign_permissions():
        try:
            for model in apps.get_models():
                defaults = getattr(model, "default_field_permissions", {})
                if not defaults:
                    continue

                content_type = HorillaContentType.objects.get_for_model(model)
                for field_name, perm in defaults.items():
                    FieldPermission.objects.get_or_create(
                        user=instance,
                        content_type=content_type,
                        field_name=field_name,
                        defaults={"permission_type": perm},
                    )
        except Exception as e:
            print(
                f"✗ Error assigning default field permissions to {instance.username}: {e}"
            )

    transaction.on_commit(assign_permissions)


@receiver(post_save, sender=Role)
def role_default_field_permissions(sender, instance, created, **kwargs):
    """
    Assign default field permissions to newly created roles.
    Also assign these permissions to all members of the role.
    """

    def assign_permissions():
        try:
            for model in apps.get_models():
                defaults = getattr(model, "default_field_permissions", {})
                if not defaults:
                    continue

                content_type = HorillaContentType.objects.get_for_model(model)

                for field_name, perm in defaults.items():
                    # Assign to role
                    FieldPermission.objects.get_or_create(
                        role=instance,
                        content_type=content_type,
                        field_name=field_name,
                        defaults={"permission_type": perm},
                    )

                    # Assign to all users in this role
                    for user in instance.users.all():
                        FieldPermission.objects.get_or_create(
                            user=user,
                            content_type=content_type,
                            field_name=field_name,
                            defaults={"permission_type": perm},
                        )

        except Exception as e:
            print(
                f"✗ Error assigning default field permissions to role '{instance.role_name}': {e}"
            )

    transaction.on_commit(assign_permissions)


@receiver(post_save, sender=FieldPermission)
@receiver(post_delete, sender=FieldPermission)
def clear_column_visibility_cache_on_permission_change(sender, instance, **kwargs):
    """
    Clear column visibility cache and clean up ListColumnVisibility records
    when field permissions are created, updated, or deleted.
    This ensures that list/kanban views reflect permission changes immediately.
    """

    def cleanup_visibility_records():
        try:
            content_type = instance.content_type
            app_label = content_type.app_label
            field_name = instance.field_name

            try:
                model = content_type.model_class()
                if not model:
                    # Fallback: try to get model using content_type.model (lowercase)
                    model = apps.get_model(
                        app_label=app_label, model_name=content_type.model
                    )
                model_name = model.__name__
            except (LookupError, AttributeError) as e:
                logger.error(
                    "Model not found: %s.%s: %s",
                    app_label,
                    content_type.model,
                    e,
                )
                return

            affected_users = []
            if instance.user:
                affected_users = [instance.user]
            elif instance.role_id and instance.role and instance.role.pk:
                affected_users = list(instance.role.users.all())

            _permission_type = None
            if hasattr(instance, "permission_type"):
                _permission_type = instance.permission_type

            for user in affected_users:
                visibility_entries = ListColumnVisibility.all_objects.filter(
                    user=user, app_label=app_label
                ).filter(Q(model_name=model_name) | Q(model_name=model_name.lower()))
                for entry in visibility_entries:
                    updated = False

                    current_permission = get_user_field_permission(
                        user, model, field_name
                    )

                    if current_permission == "hidden":
                        original_visible_fields = (
                            entry.visible_fields.copy() if entry.visible_fields else []
                        )
                        updated_visible_fields = []

                        for field_item in original_visible_fields:
                            # Handle both [verbose_name, field_name] and field_name formats
                            if (
                                isinstance(field_item, (list, tuple))
                                and len(field_item) >= 2
                            ):
                                item_field_name = field_item[1]
                            else:
                                item_field_name = field_item

                            field_matches = (
                                item_field_name == field_name
                                or item_field_name == f"get_{field_name}_display"
                                or (
                                    item_field_name.startswith("get_")
                                    and item_field_name.endswith("_display")
                                    and item_field_name.replace("get_", "").replace(
                                        "_display", ""
                                    )
                                    == field_name
                                )
                            )

                            if not field_matches:
                                updated_visible_fields.append(field_item)
                            else:
                                updated = True

                        # Remove from removed_custom_fields
                        original_removed_fields = (
                            entry.removed_custom_fields.copy()
                            if entry.removed_custom_fields
                            else []
                        )
                        updated_removed_fields = []

                        for field_item in original_removed_fields:
                            if (
                                isinstance(field_item, (list, tuple))
                                and len(field_item) >= 2
                            ):
                                item_field_name = field_item[1]
                            else:
                                item_field_name = field_item

                            # Check if this field matches the hidden field
                            field_matches = (
                                item_field_name == field_name
                                or item_field_name == f"get_{field_name}_display"
                                or (
                                    item_field_name.startswith("get_")
                                    and item_field_name.endswith("_display")
                                    and item_field_name.replace("get_", "").replace(
                                        "_display", ""
                                    )
                                    == field_name
                                )
                            )

                            if not field_matches:
                                updated_removed_fields.append(field_item)
                            else:
                                updated = True

                        if updated:
                            entry.visible_fields = updated_visible_fields
                            entry.removed_custom_fields = updated_removed_fields
                            entry.save(
                                update_fields=[
                                    "visible_fields",
                                    "removed_custom_fields",
                                ]
                            )

                    elif current_permission != "hidden":
                        try:
                            original_removed_fields = (
                                entry.removed_custom_fields.copy()
                                if entry.removed_custom_fields
                                else []
                            )
                            updated_removed_fields = []

                            for field_item in original_removed_fields:
                                if (
                                    isinstance(field_item, (list, tuple))
                                    and len(field_item) >= 2
                                ):
                                    item_field_name = field_item[1]
                                else:
                                    item_field_name = field_item

                                # Check if this field matches the now-visible field
                                field_matches = (
                                    item_field_name == field_name
                                    or item_field_name == f"get_{field_name}_display"
                                    or (
                                        item_field_name.startswith("get_")
                                        and item_field_name.endswith("_display")
                                        and item_field_name.replace("get_", "").replace(
                                            "_display", ""
                                        )
                                        == field_name
                                    )
                                )

                                if not field_matches:
                                    updated_removed_fields.append(field_item)
                                else:
                                    updated = True

                            if updated:
                                entry.removed_custom_fields = updated_removed_fields
                                entry.save(update_fields=["removed_custom_fields"])
                        except Exception as e:
                            logger.error(
                                "Error updating removed_custom_fields on permission change: %s",
                                e,
                            )

                    # Clear cache for this entry
                    cache_key = f"visible_columns_{entry.user.id}_{entry.app_label}_{entry.model_name}_{entry.context}_{entry.url_name}"
                    cache.delete(cache_key)

                # Update DetailFieldVisibility: remove hidden fields from header_fields and details_fields
                meta_model_name = getattr(model._meta, "model_name", model_name.lower())
                detail_visibility_entries = DetailFieldVisibility.all_objects.filter(
                    user=user, app_label=app_label
                ).filter(Q(model_name=model_name) | Q(model_name=meta_model_name))
                current_permission = get_user_field_permission(user, model, field_name)
                if current_permission == "hidden":
                    for detail_entry in detail_visibility_entries:

                        def _remove_field_from_list(field_list):
                            if not field_list:
                                return field_list, False
                            result = []
                            changed = False
                            for item in field_list:
                                fn = (
                                    item[1]
                                    if isinstance(item, (list, tuple))
                                    and len(item) >= 2
                                    else item
                                )
                                if fn == field_name:
                                    changed = True
                                    continue
                                if (
                                    isinstance(fn, str)
                                    and fn.startswith("get_")
                                    and fn.endswith("_display")
                                    and fn.replace("get_", "").replace("_display", "")
                                    == field_name
                                ):
                                    changed = True
                                    continue
                                result.append(item)
                            return result, changed

                        new_header, hdr_changed = _remove_field_from_list(
                            detail_entry.header_fields or []
                        )
                        new_details, det_changed = _remove_field_from_list(
                            detail_entry.details_fields or []
                        )
                        if hdr_changed or det_changed:
                            detail_entry.header_fields = new_header
                            detail_entry.details_fields = new_details
                            detail_entry.save(
                                update_fields=["header_fields", "details_fields"]
                            )

                elif current_permission != "hidden":
                    try:
                        details_excluded = set()
                        try:
                            from horilla.contrib.generics.views import HorillaDetailView

                            detail_view_class = HorillaDetailView._view_registry.get(
                                model
                            )
                            if detail_view_class:
                                base = getattr(
                                    detail_view_class, "base_excluded_fields", None
                                )
                                extra = (
                                    getattr(detail_view_class, "excluded_fields", [])
                                    or []
                                )
                                if base is not None:
                                    details_excluded = set(base) | set(extra)
                                else:
                                    details_excluded = set(extra)
                                pf = getattr(detail_view_class, "pipeline_field", None)
                                if pf:
                                    details_excluded.add(str(pf))
                                # Also include details_excluded_fields if defined
                                details_override = getattr(
                                    detail_view_class, "details_excluded_fields", None
                                )
                                if details_override is not None:
                                    details_excluded.update(details_override)
                            else:
                                details_excluded = {
                                    "id",
                                    "created_at",
                                    "updated_at",
                                    "history",
                                    "is_active",
                                    "additional_info",
                                    "created_by",
                                    "updated_by",
                                }
                        except Exception:
                            details_excluded = {
                                "id",
                                "created_at",
                                "updated_at",
                                "history",
                                "is_active",
                                "additional_info",
                                "created_by",
                                "updated_by",
                            }

                        if field_name not in details_excluded:
                            # Build field entry [verbose_name, field_name]
                            try:
                                mf = model._meta.get_field(field_name)
                                verbose_name = force_str(
                                    getattr(
                                        mf, "verbose_name", field_name.replace("_", " ")
                                    )
                                )
                                fn = (
                                    f"get_{field_name}_display"
                                    if getattr(mf, "choices", None)
                                    else field_name
                                )
                            except Exception:
                                verbose_name = field_name.replace("_", " ").title()
                                fn = field_name
                            field_entry = [verbose_name, fn]

                            def _base_field_name(fn):
                                if (
                                    isinstance(fn, str)
                                    and fn.startswith("get_")
                                    and fn.endswith("_display")
                                ):
                                    return fn.replace("get_", "").replace(
                                        "_display", ""
                                    )
                                return fn

                            # Determine where field belongs: header, details, or both
                            add_to_header = False
                            add_to_details = False
                            try:
                                from horilla.contrib.generics.views.helpers import (
                                    get_detail_field_defaults_no_request,
                                )

                                default_header, default_details = (
                                    get_detail_field_defaults_no_request(model)
                                )
                                field_base = _base_field_name(fn)
                                for item in default_header or []:
                                    existing = (
                                        item[1]
                                        if isinstance(item, (list, tuple))
                                        and len(item) >= 2
                                        else item
                                    )
                                    if _base_field_name(existing) == field_base:
                                        add_to_header = True
                                        break
                                for item in default_details or []:
                                    existing = (
                                        item[1]
                                        if isinstance(item, (list, tuple))
                                        and len(item) >= 2
                                        else item
                                    )
                                    if _base_field_name(existing) == field_base:
                                        add_to_details = True
                                        break
                                if not add_to_header and not add_to_details:
                                    add_to_details = True
                            except Exception:
                                add_to_details = True

                            def _field_already_in_list(field_list, entry):
                                if not field_list:
                                    return False
                                entry_base = _base_field_name(entry[1])
                                for item in field_list:
                                    existing_fn = (
                                        item[1]
                                        if isinstance(item, (list, tuple))
                                        and len(item) >= 2
                                        else item
                                    )
                                    if _base_field_name(existing_fn) == entry_base:
                                        return True
                                return False

                            for detail_entry in detail_visibility_entries:
                                updated = False
                                header = list(detail_entry.header_fields or [])
                                details = list(detail_entry.details_fields or [])

                                if not _field_already_in_list(
                                    header, field_entry
                                ) and not _field_already_in_list(details, field_entry):
                                    if add_to_header:
                                        header.append(field_entry)
                                        updated = True
                                    if add_to_details:
                                        details.append(field_entry)
                                        updated = True

                                if updated:
                                    update_fields = []
                                    if add_to_header:
                                        detail_entry.header_fields = header
                                        update_fields.append("header_fields")
                                    if add_to_details:
                                        detail_entry.details_fields = details
                                        update_fields.append("details_fields")
                                    if update_fields:
                                        detail_entry.save(update_fields=update_fields)
                    except Exception as e:
                        logger.error(
                            "Error re-adding field to detail visibility on permission change: %s",
                            e,
                        )

        except Exception as e:
            logger.error(
                "Error cleaning up column visibility records on permission change: %s",
                e,
            )

    transaction.on_commit(cleanup_visibility_records)


def clear_list_column_cache_for_model(content_type, affected_users=None):
    """
    Clear list column visibility cache for all users who have ListColumnVisibility
    for the given model (content_type).

    Args:
        content_type: HorillaContentType instance for the model
        affected_users: Optional list of user IDs to limit cache clearing to specific users
    """
    try:
        app_label = content_type.app_label
        model_name = (
            content_type.model_class().__name__ if content_type.model_class() else None
        )

        if not model_name:
            return

        visibility_queryset = ListColumnVisibility.all_objects.filter(
            app_label=app_label, model_name=model_name
        )

        if affected_users:
            visibility_queryset = visibility_queryset.filter(user_id__in=affected_users)

        for visibility in visibility_queryset:
            cache_key = f"visible_columns_{visibility.user.id}_{app_label}_{model_name}_{visibility.context}_{visibility.url_name}"
            cache.delete(cache_key)

    except Exception as e:
        logger.error("Error clearing list column cache: %s", e)


@receiver(post_save, sender=Company)
def assign_first_company_to_all_users(sender, instance, created, **kwargs):
    """Assign the first company created to all users"""
    if created:
        if Company.objects.count() == 1:
            User.objects.filter(company__isnull=True).update(company=instance)
