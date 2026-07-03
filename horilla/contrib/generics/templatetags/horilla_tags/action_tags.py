"""Template tags for action permissions and filtering (including intermediate models)."""

# Standard library imports
import logging

# First party imports (Horilla)
from horilla.apps import apps

# Local imports
from ._registry import register

logger = logging.getLogger(__name__)


def get_app_labels_from_context(related_obj, request, action=None):
    """
    Dynamically discover app labels from context.

    Args:
        related_obj: The related model instance
        request: The request object
        action: Optional action dict that may contain intermediate_app_label

    Returns:
        list: Ordered list of app labels to try (most likely first)
    """

    app_labels = []
    seen = set()

    if action and action.get("intermediate_app_label"):
        app_label = action.get("intermediate_app_label")
        if app_label not in seen:
            app_labels.append(app_label)
            seen.add(app_label)

    if related_obj and hasattr(related_obj, "_meta"):
        app_label = related_obj._meta.app_label
        if app_label not in seen:
            app_labels.append(app_label)
            seen.add(app_label)

    if request and hasattr(request, "resolver_match") and request.resolver_match:
        view_func = request.resolver_match.func
        if hasattr(view_func, "view_class"):
            view_class = view_func.view_class
            if hasattr(view_class, "model") and view_class.model:
                app_label = view_class.model._meta.app_label
                if app_label not in seen:
                    app_labels.append(app_label)
                    seen.add(app_label)

    if request and hasattr(request, "resolver_match") and request.resolver_match:
        url_name = request.resolver_match.url_name
        if url_name:
            if ":" in url_name:
                app_name = url_name.split(":")[0]
                if app_name not in seen:
                    app_labels.append(app_name)
                    seen.add(app_name)
            elif "_" in url_name:
                app_name = url_name.split("_")[0]
                if app_name not in seen:
                    app_labels.append(app_name)
                    seen.add(app_name)

        namespace = getattr(request.resolver_match, "namespace", None)
        if namespace and namespace not in seen:
            app_labels.append(namespace)
            seen.add(namespace)

    for app_config in apps.get_app_configs():
        if app_config.label not in seen:
            app_labels.append(app_config.label)
            seen.add(app_config.label)

    return app_labels


def get_intermediate_instance(action, related_obj, request):
    """
    Get the intermediate model instance based on action config.

    Args:
        action: Action dictionary with intermediate_model config
        related_obj: The related model instance (e.g., Department)
        request: The request object to get parent object ID

    Returns:
        The intermediate model instance or None
    """

    intermediate_model_name = action.get("intermediate_model")
    if not intermediate_model_name:
        return None

    try:
        parent_id = None
        if hasattr(request, "resolver_match") and request.resolver_match:
            parent_id = request.resolver_match.kwargs.get("pk")
        if not parent_id:
            parent_id = request.GET.get("object_id")

        if not parent_id:
            return None

        app_labels_to_try = get_app_labels_from_context(related_obj, request, action)

        intermediate_model = None
        for app_label in app_labels_to_try:
            try:
                intermediate_model = apps.get_model(app_label, intermediate_model_name)
                logger.debug(
                    "Found intermediate model '%s' in app '%s'",
                    intermediate_model_name,
                    app_label,
                )
                break
            except LookupError:
                continue

        if not intermediate_model:
            logger.warning(
                "Could not find intermediate model '%s' in any of these apps: %s",
                intermediate_model_name,
                app_labels_to_try[:5],
            )
            return None

        intermediate_field_name = action.get("intermediate_field")
        parent_field_name = action.get("parent_field")

        if not intermediate_field_name or not parent_field_name:
            logger.error(
                "Action missing 'intermediate_field' or 'parent_field' configuration"
            )
            return None

        filter_kwargs = {
            intermediate_field_name: related_obj,
            f"{parent_field_name}_id": parent_id,
        }

        intermediate_obj = intermediate_model.objects.filter(**filter_kwargs).first()

        if not intermediate_obj:
            logger.debug(
                "No %s found with filters: %s", intermediate_model_name, filter_kwargs
            )

        return intermediate_obj

    except Exception as e:
        logger.error("Error getting intermediate instance: %s", e, exc_info=True)
        return None


def has_action_permission(action, context):
    """
    Check if user has permission to perform an action on an object.
    Supports both direct object permissions and intermediate model permissions.

    Args:
        action: Action dict with permission config
        context: Dict with 'user', 'object', and optionally 'intermediate_object'

    Returns:
        bool: True if user has permission
    """
    user = context.get("user")
    obj = context.get("object")

    perm = action.get("permission")
    own_perm = action.get("own_permission")
    owner_field = action.get("owner_field")
    owner_method = action.get("owner_method")

    perms = action.get("permissions", [])
    perm_logic = action.get("permission_logic", "OR")

    if not perm and not own_perm and not owner_field or user.is_superuser:
        return True

    intermediate_config = action.get("intermediate_model")

    target_obj = obj
    if intermediate_config:
        intermediate_obj = context.get("intermediate_object")
        if intermediate_obj:
            target_obj = intermediate_obj

    if own_perm and not owner_field and not owner_method:
        raise ValueError(
            f"Action '{action.get('action')}' must define BOTH "
            "'own_permission' and ('owner_field' OR 'owner_method')."
        )

    if owner_field and owner_method:
        raise ValueError(
            f"Action '{action.get('action')}' cannot define BOTH "
            "'owner_field' AND 'owner_method'. Use only one."
        )

    if perm and user.has_perm(perm):
        return True

    if perms:
        perm_checks = [user.has_perm(p) for p in perms]

        if perm_logic.upper() == "OR":
            if any(perm_checks):
                return True
        elif perm_logic.upper() == "AND":
            if all(perm_checks):
                return True
        else:
            raise ValueError(
                f"Invalid permission_logic '{perm_logic}'. Must be 'OR' or 'AND'."
            )

    if own_perm and target_obj:
        if owner_method:
            if hasattr(target_obj, owner_method):
                method = getattr(target_obj, owner_method)
                if callable(method):
                    is_owner = method(user)
                    if is_owner and user.has_perm(own_perm):
                        return True
            else:
                raise ValueError(
                    f"Object {target_obj.__class__.__name__} does not have method '{owner_method}'"
                )

        elif owner_field:
            from horilla.contrib.core.utils import get_allowed_user_ids

            allowed_ids = get_allowed_user_ids(user)
            owner_fields = (
                owner_field if isinstance(owner_field, list) else [owner_field]
            )

            for field in owner_fields:
                owner = getattr(target_obj, field, None)
                if owner is not None:
                    owner_pk = owner.pk if hasattr(owner, "pk") else owner
                    if owner_pk in allowed_ids and user.has_perm(own_perm):
                        return True

    return False


@register.simple_tag(takes_context=True)
def filter_actions_by_permission(context, actions, data):
    """
    Return all actions, marking unauthorized ones as disabled (greyed out, no HTMX).
    Actions without any permission config are always shown as enabled.
    """
    request = context.get("request")
    user = request.user if request else None

    if not user:
        return []

    result = []

    for action in actions:
        action_context = {
            "user": user,
            "object": data,
        }

        intermediate_model_name = action.get("intermediate_model")
        if intermediate_model_name:
            intermediate_obj = get_intermediate_instance(action, data, request)
            if intermediate_obj:
                action_context["intermediate_object"] = intermediate_obj

        if has_action_permission(action, action_context):
            result.append(action)
        else:
            disabled_action = dict(action)
            disabled_action["disabled_if"] = lambda _obj: True
            result.append(disabled_action)

    return result


@register.simple_tag(takes_context=True)
def has_any_actions_for_queryset(context, actions, queryset):
    """
    Check if any object in the queryset has at least one allowed action.
    Used to determine if the Actions column should be shown in the table header.
    Supports intermediate model permission checks automatically.

    Args:
        context: template context with request
        actions: list of action dicts
        queryset: queryset of objects to check

    Returns:
        bool: True if at least one object has at least one allowed action
    """
    request = context.get("request")
    user = request.user if request else None

    if not user:
        return False

    # Actions column is always shown when actions are defined — unauthorized
    # actions are rendered as disabled icons rather than hidden entirely.
    return bool(actions)


@register.simple_tag(takes_context=True)
def col_attr_has_permission(context, col_attrs_for_field, data):
    """
    Return True if the user has permission to use this col_attr link on ``data``.

    Unlike filter_actions_by_permission (which always returns a non-empty list),
    this tag returns a plain boolean so the template can decide whether to render
    the HTMX link attrs or leave the cell as plain text.
    """
    request = context.get("request")
    user = request.user if request else None
    if not user:
        return False
    if not isinstance(col_attrs_for_field, dict):
        return True
    action_context = {"user": user, "object": data}
    return has_action_permission(col_attrs_for_field, action_context)
