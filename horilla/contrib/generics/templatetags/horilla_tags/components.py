"""Reusable component tags (inclusion tags) for Horilla templates."""

from ._registry import register

# Written out in full so the classes stay greppable.
SPINNER_SIZES = {
    "xs": "h-3 w-3",
    "sm": "h-5 w-5",
    "md": "h-6 w-6",
    "lg": "h-8 w-8",
}


@register.inclusion_tag("components/_reload_button.html", takes_context=True)
def reload_button(
    context,
    container,
    *,
    swap="outerHTML",
    url=None,
    trigger="click",
    label="click",
    indicator=None,
    button_id="reloadButton",
    hidden=True,
    **attrs,
):
    """
    Render a hidden HTMX button that refreshes ``container`` (a CSS selector).

    The button re-fetches the current page and replaces ``container`` with the same
    element taken from the response, so ``container`` is used for both ``hx-target``
    and ``hx-select``. Any other ``hx-*`` attribute is passed as a keyword with
    underscores (``hx_push_url="true"``, ``hx_select_oob="#dropdown-companies"``).
    A keyword whose name matches a generated attribute replaces it, so a different
    ``hx-select`` is ``hx_select="#other"`` and ``hx_select=""`` leaves it out.
    """

    if url is None:
        request = context.get("request")
        if request:
            query = request.GET.urlencode()
            url = f"{request.path}?{query}" if query else request.path
        else:
            url = ""

    pairs = {
        "hx-get": url,
        "hx-target": container,
        "hx-trigger": trigger,
        "hx-swap": swap,
        "hx-select": container,
        "hx-indicator": indicator,
    }

    # Custom attributes override defaults instead of creating duplicates.
    pairs.update((name.replace("_", "-"), value) for name, value in attrs.items())

    rendered = []
    for name, value in pairs.items():
        if value is None or value is False or value == "":
            continue

        rendered.append((name, None if value is True else value))

    return {
        "button_id": button_id,
        "hidden": hidden,
        "label": label,
        "attrs": rendered,
    }


@register.inclusion_tag("components/_modal_header.html")
def modal_header(title, on_close="closeModal()", button_id="", badge=None):
    """Render the standard modal header: title on the left, close button on the right.

    Usage:
        {% modal_header _("Account Hierarchy") %}
        {% modal_header _("Insert Fields") on_close="closeContentModal()" %}
    """
    return {
        "title": title,
        "on_close": on_close,
        "button_id": button_id,
        "badge": badge,
    }


@register.inclusion_tag("components/_spinner.html")
def spinner(size="lg", *, centered=False, wrapper_class=""):
    """Render the animated loading ring in the theme's primary colour.

    ``size`` is one of ``xs`` (h-3), ``sm`` (h-5), ``md`` (h-6) or ``lg`` (h-8,
    the default). ``centered=True`` wraps the ring in a
    ``flex justify-center items-center p-4`` block, the usual body of an
    ``.htmx-indicator``; ``wrapper_class`` adds classes to that block (e.g.
    ``"w-full"``). The outer element itself (``htmx-indicator``, ids, ``<li>``
    with hx-* attributes) differs per call site and stays in the template.

    Usage:
        {% spinner %}
        {% spinner "sm" %}
        {% spinner centered=True %}
    """
    if size not in SPINNER_SIZES:
        raise ValueError(
            f"Unknown spinner size {size!r}; expected one of {', '.join(SPINNER_SIZES)}"
        )
    return {
        "size_class": SPINNER_SIZES[size],
        "centered": centered,
        "wrapper_class": wrapper_class,
    }
