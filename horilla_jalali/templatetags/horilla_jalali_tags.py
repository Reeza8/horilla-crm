"""Template tags for the Jalali extension inject fragments."""

from django import template

from horilla_jalali.calendar import uses_jalali_calendar as _uses_jalali_calendar

register = template.Library()


@register.simple_tag(takes_context=True)
def uses_jalali_calendar(context):
    """Return True when the current request should use Shamsi pickers."""
    request = context.get("request")
    user = getattr(request, "user", None)
    if user is not None and not getattr(user, "is_authenticated", False):
        user = None
    return _uses_jalali_calendar(user=user)
