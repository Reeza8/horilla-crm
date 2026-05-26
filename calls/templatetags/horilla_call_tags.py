"""Template tags for Horilla Calls integration."""

from django import template

register = template.Library()


@register.simple_tag
def calls_enabled():
    """Return True if call integration is active and at least one provider is configured."""
    try:
        from calls.models import CallIntegrationSetting, CallProvider
        setting = CallIntegrationSetting.objects.first()
        if not setting or not setting.is_enabled:
            return False
        return CallProvider.objects.filter(status=CallProvider.STATUS_ACTIVE).exists()
    except Exception:
        return False


@register.simple_tag
def get_phone_number(obj):
    """Return the first non-empty phone number found on any CRM model instance."""
    for field in ("contact_number", "phone", "mobile", "phone_number", "mobile_number"):
        val = getattr(obj, field, None)
        if val:
            return val
    return ""
