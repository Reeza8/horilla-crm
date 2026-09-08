"""
Runtime hooks so Multiple Choice custom fields keep every selected value
on Horilla multi-step create forms.

Horilla's wizard copies ``request.POST[key]``, which is only the last value
for a multi-select. Patch that from the custom_fields app so we do not edit
Horilla sources.
"""

import logging

from custom_fields.models import CustomFieldDefinition
from custom_fields.utils import (
    choice_values_from_data,
    is_custom_field_name,
    parse_custom_field_pk,
)

logger = logging.getLogger(__name__)

_PATCHED = False


def overlay_custom_choice_post_values(post_data, form_data):
    """
    Replace wizard session values for ``cf_*`` Multiple Choice fields with
    the full ``getlist`` from POST. Returns True when ``form_data`` changed.
    """
    if not post_data or form_data is None:
        return False
    changed = False
    keys = list(getattr(post_data, "keys", lambda: post_data)())
    for key in keys:
        if not is_custom_field_name(key):
            continue
        pk = parse_custom_field_pk(key)
        if pk is None:
            continue
        try:
            defn = CustomFieldDefinition.objects.get(pk=pk)
        except CustomFieldDefinition.DoesNotExist:
            continue
        if defn.field_type != "choice":
            continue
        if hasattr(post_data, "getlist"):
            raw = post_data.getlist(key)
        else:
            raw = post_data.get(key)
        form_data[key] = choice_values_from_data(raw)
        changed = True
    return changed


def install_form_patches():
    """Monkey-patch Horilla multi-step POST collection without editing its file."""
    global _PATCHED
    if _PATCHED:
        return

    from horilla.contrib.generics.views.multi_form import HorillaMultiStepFormView

    original_get_form_kwargs = HorillaMultiStepFormView.get_form_kwargs

    def patched_get_form_kwargs(self):
        kwargs = original_get_form_kwargs(self)
        if getattr(self.request, "method", "") != "POST":
            return kwargs
        form_data = kwargs.get("form_data")
        if form_data is None:
            return kwargs
        try:
            if overlay_custom_choice_post_values(self.request.POST, form_data):
                kwargs["form_data"] = form_data
                kwargs["data"] = form_data
                storage_key = getattr(self, "storage_key", None)
                if storage_key:
                    self.request.session[storage_key] = form_data
        except Exception:
            logger.exception("custom_fields: could not keep multi-select POST values")
        return kwargs

    HorillaMultiStepFormView.get_form_kwargs = patched_get_form_kwargs
    _PATCHED = True
