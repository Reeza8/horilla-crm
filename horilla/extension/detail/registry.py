"""
Registry for _inherit_detail extension specs (populated at class definition time).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

DETAIL_EXTENSION_REGISTRY: dict[str, list["DetailExtensionSpec"]] = {}

DETAIL_COMPOSED_MAP: dict[str, type] = {}


@dataclass
class DetailExtensionSpec:
    """Captured contribution from a DetailExtension subclass."""

    inherit_detail: str
    class_name: str
    module: str
    extension_app_label: str
    priority: int = 0
    class_attrs: dict[str, Any] = field(default_factory=dict)
    body_insert: list[tuple[str, str | tuple]] = field(default_factory=list)
    body_append: list[str | tuple] = field(default_factory=list)
    fieldsets_insert: list[tuple[str, str]] = field(default_factory=list)
    header_fields_insert: list[tuple[str, str | tuple]] = field(default_factory=list)
    header_fields_append: list[str | tuple] = field(default_factory=list)
    excluded_fields_append: list[str] = field(default_factory=list)
    split_excluded_fields_append: list[str] = field(default_factory=list)
    actions_append: list[Any] = field(default_factory=list)
    badge_append: list[Any] = field(default_factory=list)
    breadcrumbs_append: list[Any] = field(default_factory=list)
    scalar_overrides: dict[str, Any] = field(default_factory=dict)
    override_attrs: frozenset[str] = frozenset()


def register_detail_extension(spec: DetailExtensionSpec) -> None:
    """Append an extension spec for a target detail view path."""
    DETAIL_EXTENSION_REGISTRY.setdefault(spec.inherit_detail, []).append(spec)
    from horilla.extension.detail.cache import invalidate_after_registry_change

    invalidate_after_registry_change()


def get_detail_extensions_for(target_path: str) -> list[DetailExtensionSpec]:
    """Return extension specs for a target, sorted by priority then registration order."""
    specs = list(DETAIL_EXTENSION_REGISTRY.get(target_path, []))
    specs.sort(key=lambda s: (s.priority, s.module, s.class_name))
    return specs
