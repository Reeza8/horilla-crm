"""
Horilla _inherit_form — compose concrete target forms from extension apps.
"""

from horilla.extension.forms.bootstrap import apply_form_extensions
from horilla.extension.forms.debug import get_form_extensions, print_form_mro
from horilla.extension.forms.metaclass import FormExtension
from horilla.extension.forms.registry import FORM_COMPOSED_MAP, FORM_EXTENSION_REGISTRY
from horilla.extension.forms.resolve import (
    clear_form_extension_cache,
    resolve_form_class,
)

__all__ = [
    "FormExtension",
    "FORM_EXTENSION_REGISTRY",
    "FORM_COMPOSED_MAP",
    "apply_form_extensions",
    "resolve_form_class",
    "clear_form_extension_cache",
    "get_form_extensions",
    "print_form_mro",
]
