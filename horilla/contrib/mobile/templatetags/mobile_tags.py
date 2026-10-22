"""
Template tags for the mobile layout.
"""

# Third-party imports (Django)
from django import template
from django.templatetags.static import static
from django.utils.http import urlencode
from django.utils.safestring import SafeString

# First party imports (Horilla)
from horilla.auth.models import User
from horilla.core.exceptions import FieldDoesNotExist
from horilla.utils.html import strip_tags
from horilla.utils.translation import gettext as _
from horilla.contrib.generics.forms.condition_fields import get_condition_field_value
from horilla.contrib.generics.templatetags.horilla_tags.display_tags import (
    display_field_value,
)

# Local imports
from ..utils import get_asset_version, local_digits, user_display_name

register = template.Library()


@register.simple_tag
def mobile_static(path):
    """
    Return the static URL for ``path`` with the mobile asset version appended.

    Only URLs built with this tag are cached by the mobile service worker.
    """
    url = static(path)
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}{urlencode({'v': get_asset_version()})}"


@register.simple_tag
def mobile_field_value(obj, field_name, user):
    """
    Display value of ``field_name`` on ``obj`` as plain text, formatted like
    the desktop. Long text loses any HTML the desktop editor stored.

    Model fields go through ``display_field_value`` (choices, foreign keys,
    dates in the user's timezone and format, currency). Users are shown by
    name: the desktop renders them as a link chip, which would nest a link
    inside the phone's row link. Other names, such as custom fields
    (``cf_<id>``), are read through the app that owns them.
    """
    try:
        field = obj._meta.get_field(field_name)
    except FieldDoesNotExist:
        try:
            value = get_condition_field_value(field_name, obj)
        except Exception:  # pylint: disable=broad-except
            return ""
        return "" if value is None else value

    if field.is_relation and field.related_model is User:
        value = getattr(obj, field_name, None)
        if value is None:
            return ""
        if hasattr(value, "all"):
            return ", ".join(user_display_name(member) for member in value.all())
        return user_display_name(value)

    if field.get_internal_type() == "BooleanField":
        value = getattr(obj, field_name, None)
        if value is None:
            return ""
        return _("Yes") if value else _("No")

    value = display_field_value(obj, field_name, user)
    # Desktop long text can hold the rich-text editor's HTML; the phone shows
    # its text.
    if isinstance(value, SafeString) or field.get_internal_type() == "TextField":
        return strip_tags(str(value)).strip()
    return value


@register.simple_tag
def mobile_joined_values(obj, field_names, user):
    """Values of ``field_names`` on ``obj`` in one line, skipping empty ones."""
    values = (str(mobile_field_value(obj, name, user)).strip() for name in field_names)
    return " ".join(value for value in values if value)


@register.filter
def color_tint(color):
    """``#RRGGBB`` -> the same color at low opacity, for a label background."""
    return f"{color}1f" if isinstance(color, str) and len(color) == 7 else ""


@register.filter(name="local_digits")
def local_digits_filter(value):
    """A count or number in the active language's own digits."""
    return local_digits(value)
