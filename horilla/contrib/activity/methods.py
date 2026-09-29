"""
Helper methods for Activity modules
"""


def is_related_record_visible(related):
    """
    Return True if ``related`` is in its model's default (company-filtered)
    queryset, i.e. its own detail page and Details tab would find it.
    """
    return related.__class__._default_manager.filter(pk=related.pk).exists()


def get_related_record_url(related, user):
    """Return the related record's detail URL if the user may open it, else ""."""
    from horilla.contrib.generics.views.details import check_record_access
    from horilla.contrib.utils.methods import get_section_info_for_model

    get_detail_url = getattr(related, "get_detail_url", None)
    if not callable(get_detail_url) or not user or not user.is_authenticated:
        return ""
    if not check_record_access(user, related):
        return ""
    if not is_related_record_visible(related):
        return ""
    url = str(get_detail_url())
    # Open the record's own module in the side menu, like detail breadcrumbs do.
    section = get_section_info_for_model(related.__class__).get("section")
    if section:
        url = f"{url}{'&' if '?' in url else '?'}section={section}"
    return url


def get_related_record_detail_url_name(related):
    """
    Return the ``detail_url_name`` the related record's own detail page passes
    to its Details tab (e.g. ``leads_detail``), so the Related To tab shows the
    same saved field selection. Returns "" when it can't be resolved.
    """
    from horilla.urls import resolve

    get_detail_url = getattr(related, "get_detail_url", None)
    if not callable(get_detail_url):
        return ""
    try:
        resolved = resolve(str(get_detail_url()))
    except Exception:
        return ""
    url_name = resolved.url_name or ""
    view_class = getattr(resolved.func, "view_class", None)
    get_scope = getattr(view_class, "get_detail_field_visibility_scope", None)
    if url_name and callable(get_scope):
        try:
            scope = view_class().get_detail_field_visibility_scope(related)
        except Exception:
            scope = ""
        if scope:
            url_name = f"{url_name}:{scope}"
    return url_name
