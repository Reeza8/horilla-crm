"""
Registry for _inherit_form extension specs (populated at class definition time).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# target form path -> ordered extension specs
FORM_EXTENSION_REGISTRY: dict[str, list["ExtensionSpec"]] = {}

# target form path -> composed form class (filled by bootstrap)
FORM_COMPOSED_MAP: dict[str, type] = {}

LAYOUT_KEYS = frozenset(
    {
        "field_order_insert",
        "field_order_append",
        "step_fields_insert",
        "step_fields_append",
        "fieldsets_insert",
    }
)


@dataclass
class ExtensionSpec:  # pylint: disable=too-many-instance-attributes
    """Captured contribution from a FormExtension subclass."""

    inherit_form: str
    class_name: str
    module: str
    extension_app_label: str
    priority: int = 0
    declared_fields: dict[str, Any] = field(default_factory=dict)
    meta_attrs: dict[str, Any] = field(default_factory=dict)
    class_attrs: dict[str, Any] = field(default_factory=dict)
    field_order_insert: list[tuple[str, str]] = field(default_factory=list)
    field_order_append: list[str] = field(default_factory=list)
    step_fields_insert: dict[int, list[tuple[str, str]]] = field(default_factory=dict)
    step_fields_append: dict[int, list[str]] = field(default_factory=dict)
    fieldsets_insert: list[tuple[str, str]] = field(default_factory=list)
    override_fields: frozenset[str] = frozenset()


def register_extension(spec: ExtensionSpec) -> None:
    """Append an extension spec for a target form path."""
    FORM_EXTENSION_REGISTRY.setdefault(spec.inherit_form, []).append(spec)


def get_extensions_for(target_path: str) -> list[ExtensionSpec]:
    """Return extension specs for a target, sorted by priority then registration order."""
    specs = list(FORM_EXTENSION_REGISTRY.get(target_path, []))
    specs.sort(key=lambda s: (s.priority, s.module, s.class_name))
    return specs
