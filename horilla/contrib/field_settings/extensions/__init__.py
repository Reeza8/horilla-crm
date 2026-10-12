"""Extension registrations for field settings.

Importing this package (it is listed in ``AppConfig.auto_import_modules``)
imports every submodule below, each of which registers its own extensions on
import: custom fields (view, forms, condition field, detail, filter, mixin,
list), field requirements and form layouts.
"""

from . import (  # noqa: F401
    custom_fields_condition_field,
    custom_fields_detail,
    custom_fields_filter,
    custom_fields_forms,
    custom_fields_list,
    custom_fields_mixin,
    custom_fields_view,
    field_requirements,
    form_layouts,
)
