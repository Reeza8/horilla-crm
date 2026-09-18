"""
Horilla _inherit_mixin — extend a bare mixin class or a module-level
function that no other ``_inherit_*`` mechanism can reach.

Every other extension package (forms, list, kanban, card, detail,
detail_section, filter, nav, view, tab, formatting) resolves its target
lazily, per request or per call, through an ``as_view()`` wrapper or a
``get_*_class()``/``get_datetime_formatter()`` call — a real dispatch point
where a composed subclass can be swapped in. A bare mixin (mixed into
consumers only through ordinary Python inheritance, never itself
instantiated or resolved) and a bare module-level function have no such
call site at all, so this package applies extensions directly onto the
target once, at startup, instead of composing and resolving a subclass —
see ``compose.py``.
"""

from horilla.extension.mixin.bootstrap import apply_mixin_extensions
from horilla.extension.mixin.debug import (
    get_mixin_extensions,
    is_mixin_extension_applied,
    print_mixin_extension_chain,
)
from horilla.extension.mixin.metaclass import MixinExtension
from horilla.extension.mixin.registry import (
    MIXIN_EXTENSION_REGISTRY,
    MIXIN_APPLIED_MAP,
)

__all__ = [
    "MixinExtension",
    "MIXIN_EXTENSION_REGISTRY",
    "MIXIN_APPLIED_MAP",
    "apply_mixin_extensions",
    "get_mixin_extensions",
    "is_mixin_extension_applied",
    "print_mixin_extension_chain",
]
