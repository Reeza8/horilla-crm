"""
Version information for the field requirements app.
"""

# First party imports (Horilla)
from horilla.utils.translation import gettext_lazy as _

__version__ = "1.0.0"
__module_name__ = "Field Requirements"
__release_date__ = ""
__description__ = _(
    "Configure which fields are required or optional on opted-in models, per company."
)
__icon__ = ""

__1_0_0__ = _(
    "Register field requirements as a self-contained contrib feature. Lead and "
    "Opportunity opt in through the feature registry; models that cannot store "
    "an empty value cannot be relaxed. Per-company FieldRequirement rows "
    "resolve through get_field_requirements_for_model."
)
