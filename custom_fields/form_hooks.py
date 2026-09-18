"""
Shared helper so Multiple Choice custom fields keep every selected value on
Horilla multi-step create forms.

Horilla's wizard copies ``request.POST[key]``, which is only the last value
for a multi-select. ``overlay_custom_choice_post_values`` is consumed by
``CustomFieldMultiStepFormKwargsExtension`` in
``custom_fields/view_extensions.py``, registered through ``ViewExtension``/
``_inherit_view`` targeting the shared ``HorillaMultiStepFormView`` base
class every wizard form view inherits — see that class's docstring for how
base-class targeting works.
"""

from custom_fields.models import CustomFieldDefinition
from custom_fields.utils import (
    choice_values_from_data,
    is_custom_field_name,
    parse_custom_field_pk,
)


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
