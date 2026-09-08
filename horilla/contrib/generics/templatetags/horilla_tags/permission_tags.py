"""Template tags for permission checks."""

# First party imports (Horilla)
from horilla.menu.sub_section_menu import get_sub_section_menu

# Local imports
from ._registry import register


@register.simple_tag(takes_context=True)
def has_perm(context, perm_name):
    """
    Usage: {% has_perm "core.view_horillauser" as can_view_horillauser %}
    """
    return not perm_name or context["request"].user.has_perm(perm_name)


@register.filter
def has_super_user(user, perm_data):
    """
    Check if the user is superuser OR has the required permissions.

    - `perm_data` can be:
        - a single permission string
        - a list/tuple of permissions
        - a dict like {"perms": [...], "all_perms": True/False}

    Default behavior:
      - OR check: user needs **any one** of the permissions.
      - AND check: if all_perms=True, user must have **all** permissions.
    """
    if not user or not user.is_authenticated:
        return False

    if user.is_superuser:
        return True

    if isinstance(perm_data, str):
        return user.has_perm(perm_data)

    if isinstance(perm_data, (list, tuple)):
        return any(user.has_perm(perm) for perm in perm_data)

    if isinstance(perm_data, dict):
        perms = perm_data.get("perms", [])
        all_perms = perm_data.get("all_perms", False)

        if not perms:
            return True

        if all_perms:
            return all(user.has_perm(perm) for perm in perms)

        return any(user.has_perm(perm) for perm in perms)
    return False


@register.simple_tag
def has_section_perm_url(user, section_name):
    """
    Check if the user can see at least one sub-item in a section.
    Returns the first accessible URL if permissions match.
    """
    if not user or not user.is_authenticated:
        return False

    sub_section_items = get_sub_section_menu().get(section_name, [])
    if not sub_section_items:
        return "/"

    for item in sub_section_items:
        perm_data = item.get("perm", {})

        if not perm_data or not perm_data.get("perms"):
            return item.get("url")

        perms = perm_data.get("perms", [])
        all_perms = perm_data.get("all_perms", False)

        if all_perms:
            if all(user.has_perm(perm) for perm in perms):
                return item.get("url")
        else:
            if any(user.has_perm(perm) for perm in perms):
                return item.get("url")

    return False
