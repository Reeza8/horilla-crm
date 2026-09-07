"""
Horilla _inherit_tab — compose HorillaTabView subclasses from extension apps.

Resolution hooks live on ``HorillaTabView.as_view`` so concrete tab views
(e.g. ``CompanyInformationTabView``) pick up extensions automatically.
"""

from horilla.extension.tab.bootstrap import apply_tab_extensions
from horilla.extension.tab.metaclass import TabExtension
from horilla.extension.tab.registry import TAB_COMPOSED_MAP, TAB_EXTENSION_REGISTRY
from horilla.extension.tab.resolve import (
    clear_tab_extension_cache,
    resolve_tab_view_class,
)

__all__ = [
    "TabExtension",
    "TAB_EXTENSION_REGISTRY",
    "TAB_COMPOSED_MAP",
    "apply_tab_extensions",
    "resolve_tab_view_class",
    "clear_tab_extension_cache",
]
