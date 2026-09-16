"""
Registry for _inherit_detail_section extension specs (populated at class definition time).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

DETAIL_SECTION_EXTENSION_REGISTRY: dict[str, list["DetailSectionExtensionSpec"]] = {}

DETAIL_SECTION_COMPOSED_MAP: dict[str, type] = {}


@dataclass
class DetailSectionExtensionSpec:
    """Captured contribution from a DetailSectionExtension subclass."""

    inherit_detail_section: str
    class_name: str
    module: str
    extension_app_label: str
    priority: int = 0
    class_attrs: dict[str, Any] = field(default_factory=dict)
    body_insert: list[tuple[str, str | tuple]] = field(default_factory=list)
    body_append: list[str | tuple] = field(default_factory=list)
    excluded_fields_append: list[str] = field(default_factory=list)
    include_fields_append: list[str] = field(default_factory=list)
    override_attrs: frozenset[str] = frozenset()


def register_detail_section_extension(spec: DetailSectionExtensionSpec) -> None:
    """Append an extension spec for a target detail-section view path."""
    DETAIL_SECTION_EXTENSION_REGISTRY.setdefault(
        spec.inherit_detail_section, []
    ).append(spec)
    from horilla.extension.detail_section.cache import invalidate_after_registry_change

    invalidate_after_registry_change()


def get_detail_section_extensions_for(
    target_path: str,
) -> list[DetailSectionExtensionSpec]:
    """Return extension specs for a target, sorted by priority then registration order."""
    specs = list(DETAIL_SECTION_EXTENSION_REGISTRY.get(target_path, []))
    specs.sort(key=lambda s: (s.priority, s.module, s.class_name))
    return specs
