"""Template tags for context unpacking and URL-based active/open state."""

# Local imports
from ._registry import register


@register.simple_tag(takes_context=True)
def unpack_context(context, data_dict):
    """
    Add each key/value from data_dict to the current template context.
    """
    if isinstance(data_dict, dict):
        for key, value in data_dict.items():
            context[key] = value
    return ""


@register.simple_tag(takes_context=True)
def is_active(context, *url_names):
    """
    Works with either:
    - A list of URLs: {% is_active item.active_urls %}
    - One or more URL strings: {% is_active "url_name1" "url_name2" %}
    """
    request = context.get("request")
    if not request or not request.resolver_match:
        return ""

    current_view = request.resolver_match.view_name
    current_path = request.path

    urls = []
    for arg in url_names:
        if isinstance(arg, (list, tuple)):
            urls.extend(arg)
        else:
            urls.append(arg)

    for url in urls:
        if url in (current_view, current_path):
            return "text-primary-600"

    return ""


@register.simple_tag(takes_context=True)
def is_open(context, *url_names):
    """Return 'open' when the current request matches any of the provided URLs.

    The function accepts a mix of argument types:
    - Strings representing view names or path strings
    - Dicts with a 'url' key
    - Lists/tuples containing any of the above

    It normalizes inputs into a set and checks against the current view name
    and the current path (without trailing slash).
    """
    request = context.get("request")
    if not request or not request.resolver_match:
        return ""

    current_path = request.path
    current_view_name = request.resolver_match.view_name

    all_urls = set()

    for item in url_names:
        if isinstance(item, dict) and "url" in item:
            all_urls.add(item["url"].rstrip("/"))
        elif isinstance(item, (list, tuple)):
            for sub_item in item:
                if isinstance(sub_item, dict) and "url" in sub_item:
                    all_urls.add(sub_item["url"].rstrip("/"))
                elif isinstance(sub_item, str):
                    all_urls.add(sub_item)
        elif isinstance(item, str):
            all_urls.add(item)

    if current_view_name in all_urls or current_path.rstrip("/") in all_urls:
        return "open"
    return ""


@register.simple_tag(takes_context=True)
def is_open_collapse(context, *url_names):
    """
    Returns 'rotate-90' if the current view matches any given URL or view name.
    Handles both cases:
      1. A tuple of dictionaries containing 'url' keys
      2. A tuple of view name strings
    """
    request = context.get("request")
    if not request or not request.resolver_match:
        return ""

    current_view = request.resolver_match.view_name
    current_path = request.path

    urls_to_check = set()

    for item in url_names:
        if isinstance(item, (list, tuple)):
            for entry in item:
                if isinstance(entry, dict) and "url" in entry:
                    urls_to_check.add(entry["url"])
        elif isinstance(item, str):
            urls_to_check.add(item)

    return (
        "rotate-90"
        if current_view in urls_to_check or current_path in urls_to_check
        else ""
    )
