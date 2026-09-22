"""
Version information for the form layouts app.
"""

# First party imports (Horilla)
from horilla.utils.translation import gettext_lazy as _

__version__ = "1.1.0"
__module_name__ = "Form Layouts"
__release_date__ = ""
__description__ = _(
    "Choose which fields appear on the form of opted-in models, and in what "
    "order, per company."
)
__icon__ = ""

__1_1_0__ = _(
    'Offer the saved layout as an opt-in "Custom Layout" form mode next to '
    "the default form, instead of redirecting create requests to it. Applies "
    "to edit requests as well as create; the default form and the wizard are "
    "never intercepted, and a hidden optional field never loses its stored "
    "value on an existing record."
)

__1_0_0__ = _(
    "Register form layouts as a self-contained contrib feature. Lead and "
    "Opportunity opt in through the feature registry. Per-company "
    "FormLayoutField rows hide optional fields and reorder the single-page "
    "create form; a model with a saved layout opens that form instead of the "
    "multi-step wizard. Edit forms are never changed."
)
