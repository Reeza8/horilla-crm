"""
Horilla html - re-exports django.utils.html for consistent imports.

Use: from horilla.utils.html import format_html
     from horilla.utils.html import escape, strip_tags, ...
"""

from django.utils.html import (
    avoid_wrapping,
    conditional_escape,
    escape,
    escapejs,
    format_html,
    format_html_join,
    html_safe,
    json_script,
    linebreaks,
    strip_spaces_between_tags,
    strip_tags,
    urlize,
)

__all__ = [
    "avoid_wrapping",
    "conditional_escape",
    "escape",
    "escapejs",
    "format_html",
    "format_html_join",
    "html_safe",
    "json_script",
    "linebreaks",
    "strip_spaces_between_tags",
    "strip_tags",
    "urlize",
]
