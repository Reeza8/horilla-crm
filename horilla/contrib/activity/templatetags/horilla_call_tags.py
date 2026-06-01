"""Template tags for optional Calls integration — used by activity templates."""

from django import template
from django.apps import apps

register = template.Library()


@register.simple_tag
def calls_enabled():
    """Return True if the calls app is installed."""
    return apps.is_installed("calls")


@register.simple_tag
def get_phone_number(obj):
    """Return the first non-empty phone number found on any CRM model instance."""
    for field in ("contact_number", "phone", "mobile", "phone_number", "mobile_number"):
        val = getattr(obj, field, None)
        if val:
            return val
    return ""
