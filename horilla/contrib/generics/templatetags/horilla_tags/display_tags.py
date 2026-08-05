"""Template tags for displaying field values and currency."""

# Standard library imports
import ast
import json

# Third-party imports (Django)
from django.db.models.fields.json import JSONField
from django.template.loader import render_to_string

# First party imports (Horilla)
from horilla.auth.models import User
from horilla.contrib.core.models import MultipleCurrency
from horilla.contrib.core.utils import get_currency_display_value
from horilla.utils.html import format_html_join

# Local imports
from ._registry import register
from ._shared import _get_request_user_company, format_datetime_value


def render_user_chip(target_user, viewer):
    """
    Render a linked user chip when the viewer can view users; otherwise plain text.
    """

    if not isinstance(target_user, User):
        return str(target_user) if target_user is not None else ""

    if (
        not viewer
        or not viewer.is_authenticated
        or not viewer.has_perm(f"{User._meta.app_label}.view_{User._meta.model_name}")
    ):
        return str(target_user)

    get_full_name = getattr(target_user, "get_full_name", None)
    full_name = get_full_name().strip() if callable(get_full_name) else ""

    if not full_name:
        full_name = getattr(target_user, "username", None) or str(target_user)

    get_detail_view_url = getattr(target_user, "get_detail_view_url", None)
    detail_url = str(get_detail_view_url()) if callable(get_detail_view_url) else ""

    return render_to_string(
        "user_chip.html",
        {
            "detail_url": detail_url,
            "avatar_url": target_user.get_avatar(),
            "full_name": full_name,
        },
    )


@register.simple_tag
def display_field_value(obj, field_name, user):
    """
    Template tag to display field value with automatic currency formatting,
    datetime timezone conversion, and custom formatting

    Usage in template:
    {% display_field_value obj field_name request.user %}

    Works automatically if model has CURRENCY_FIELDS attribute
    Handles datetime fields with user's timezone and format preferences
    """
    if (
        hasattr(obj.__class__, "CURRENCY_FIELDS")
        and field_name in obj.__class__.CURRENCY_FIELDS
    ):
        return get_currency_display_value(obj, field_name, user)

    if hasattr(obj, "get_field_display"):
        return obj.get_field_display(field_name, user)

    value = getattr(obj, field_name, None)

    if value is None:
        return ""

    try:
        _field = obj._meta.get_field(field_name)
    except Exception:
        _field = None
    if isinstance(_field, JSONField):
        if isinstance(value, str) and value.strip():
            s = value.strip()
            if (s.startswith("[") and s.endswith("]")) or (
                s.startswith("{") and s.endswith("}")
            ):
                try:
                    value = json.loads(s)
                except json.JSONDecodeError:
                    try:
                        value = ast.literal_eval(s)
                    except (ValueError, SyntaxError):
                        pass
        if isinstance(value, (list, tuple)):
            return ", ".join(
                str(v).strip() for v in value if v is not None and str(v).strip()
            )
        if isinstance(value, dict):
            if not value:
                return ""
            return ", ".join(f"{k}: {v}" for k, v in value.items())
        return str(value) if value else ""

    _, _, company = _get_request_user_company()

    formatted = format_datetime_value(
        value, user=user, company=company, convert_timezone=True
    )
    if formatted is not None:
        return formatted

    if hasattr(value, "all"):
        related_objects = list(value.all())
        if not related_objects:
            return ""
        if all(isinstance(item, User) for item in related_objects):
            return format_html_join(
                " ",
                "{}",
                ((render_user_chip(item, user),) for item in related_objects),
            )
        return ", ".join(str(item) for item in related_objects)

    try:
        field = obj._meta.get_field(field_name)
        if hasattr(field, "choices") and field.choices:
            return dict(field.choices).get(value, value)
    except Exception:
        pass

    if isinstance(value, User):
        return render_user_chip(value, user)

    if hasattr(value, "__str__"):
        return str(value)

    return value


@register.filter
def format_currency(value, user):
    """Template filter for currency formatting"""
    if not value:
        return ""

    user_currency = MultipleCurrency.get_user_currency(user)
    if user_currency:
        return user_currency.display_with_symbol(value)

    return str(value)


@register.filter
def shortname(value):
    """Filter to get short name (initials) from a full name string"""
    if not value:
        return ""

    words = value.strip().split()

    if len(words) >= 2:
        return (words[0][0] + words[1][0]).upper()

    return words[0][0].upper()
