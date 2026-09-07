"""
Version information for the custom_fields app.
"""

# First party imports (Horilla)
from horilla.utils.translation import gettext_lazy as _

__version__ = "1.0.0"
__module_name__ = "Custom Fields"
__release_date__ = ""
__description__ = _(
    "Define extra fields on Leads and Opportunities. Configure them in "
    "Settings and use them on create/edit forms, detail views, list columns, "
    "filters, and exports."
)
__icon__ = "assets/icons/custom-field.svg"

__1_0_0__ = _(
    "Add a Custom Fields settings app for Leads and Opportunities. Support "
    "small text, large text, number, and multiple choice fields. Inject values "
    "into create/edit forms, detail views, list columns, record filters, and "
    "exports without changing Horilla core."
)
