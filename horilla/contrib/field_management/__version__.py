"""
Version information for the field settings app.
"""

# First party imports (Horilla)
from horilla.utils.translation import gettext_lazy as _

__version__ = "1.0.0"
__module_name__ = "Field Management"
__release_date__ = ""
__description__ = _(
    "Configure fields on opted-in models: add custom fields, choose which "
    "fields are required or optional, and set which fields appear on a form "
    "and in what order, per company."
)
__icon__ = "assets/icons/field-requirement.svg"

__1_0_0__ = _(
    "Merge the Custom Fields, Field Requirements and Form Layouts apps into one "
    "Field Management app with a single Settings menu entry. Feature registry "
    "names are unchanged; existing installs are upgraded by migrate "
    "alone, keeping data and permissions."
)
