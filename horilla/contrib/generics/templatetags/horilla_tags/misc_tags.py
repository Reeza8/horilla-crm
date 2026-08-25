"""Miscellaneous template tags."""

from django.utils.encoding import force_str

# First party imports (Horilla)
from horilla.auth.models import User
from horilla.utils.translation import gettext as _

# Local imports
from ._registry import register


@register.simple_tag
def empty_add_message(model_verbose_name):
    """Complete empty-state sentence with the translated model name interpolated."""
    return _("Nothing to show yet. Please add your %(model)s.") % {
        "model": force_str(model_verbose_name)
    }


@register.simple_tag
def get_user_model_meta():
    """
    Get the User model metadata
    Returns: dict with app_label, model_name, and model_name_original
    """
    return {
        "app_label": User._meta.app_label,
        "model_name": User._meta.model_name,
        "model_class_name": User.__name__,
    }
