"""
Horilla _inherit_detail_section — compose HorillaDetailSectionView from extension apps.
"""

from horilla.extension.detail_section.bootstrap import apply_detail_section_extensions
from horilla.extension.detail_section.metaclass import DetailSectionExtension
from horilla.extension.detail_section.registry import (
    DETAIL_SECTION_COMPOSED_MAP,
    DETAIL_SECTION_EXTENSION_REGISTRY,
)
from horilla.extension.detail_section.resolve import (
    clear_detail_section_extension_cache,
    get_resolved_detail_section_view_path,
    resolve_detail_section_view_class,
)

__all__ = [
    "DetailSectionExtension",
    "DETAIL_SECTION_EXTENSION_REGISTRY",
    "DETAIL_SECTION_COMPOSED_MAP",
    "apply_detail_section_extensions",
    "resolve_detail_section_view_class",
    "get_resolved_detail_section_view_path",
    "clear_detail_section_extension_cache",
]
