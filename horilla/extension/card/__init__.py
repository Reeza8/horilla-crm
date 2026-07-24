"""
Horilla _inherit_card — compose concrete target card views from extension apps.
"""

from horilla.extension.card.bootstrap import apply_card_extensions
from horilla.extension.card.debug import get_card_extensions, print_card_view_mro
from horilla.extension.card.metaclass import CardExtension
from horilla.extension.card.registry import CARD_COMPOSED_MAP, CARD_EXTENSION_REGISTRY
from horilla.extension.card.resolve import (
    clear_card_extension_cache,
    resolve_card_view_class,
)

__all__ = [
    "CardExtension",
    "CARD_EXTENSION_REGISTRY",
    "CARD_COMPOSED_MAP",
    "apply_card_extensions",
    "resolve_card_view_class",
    "clear_card_extension_cache",
    "get_card_extensions",
    "print_card_view_mro",
]
