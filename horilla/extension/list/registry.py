"""
Registry for _inherit_list extension specs (populated at class definition time).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

LIST_EXTENSION_REGISTRY: dict[str, list["ListExtensionSpec"]] = {}

LIST_COMPOSED_MAP: dict[str, type] = {}

# concrete list view class -> composed subclass, resolved lazily when the
# extension is registered on a base class rather than the concrete view
# itself (see horilla.extension.list.resolve._resolve_via_base_class).
# Keyed by class object, not path, since these are discovered on demand
# rather than enumerated from LIST_EXTENSION_REGISTRY.
LIST_BASE_COMPOSED_MAP: dict[type, type | None] = {}


@dataclass
class ListExtensionSpec:
    """Captured contribution from a ListExtension subclass."""

    inherit_list: str
    class_name: str
    module: str
    extension_app_label: str
    priority: int = 0
    class_attrs: dict[str, Any] = field(default_factory=dict)
    columns_insert: list[tuple[str, str | tuple]] = field(default_factory=list)
    columns_append: list[str | tuple] = field(default_factory=list)
    bulk_update_fields_append: list[str] = field(default_factory=list)
    export_exclude_append: list[str] = field(default_factory=list)
    exclude_columns_append: list[str] = field(default_factory=list)
    actions_append: list[Any] = field(default_factory=list)
    custom_bulk_actions_append: list[Any] = field(default_factory=list)
    additional_action_button_append: list[Any] = field(default_factory=list)
    exclude_quick_filter_fields_append: list[str] = field(default_factory=list)
    exclude_columns_from_sorting_append: list[str] = field(default_factory=list)
    scalar_overrides: dict[str, Any] = field(default_factory=dict)
    override_attrs: frozenset[str] = frozenset()


def register_list_extension(spec: ListExtensionSpec) -> None:
    """Append an extension spec for a target list view path."""
    LIST_EXTENSION_REGISTRY.setdefault(spec.inherit_list, []).append(spec)
    from horilla.extension.list.cache import invalidate_after_registry_change

    invalidate_after_registry_change()


def get_list_extensions_for(target_path: str) -> list[ListExtensionSpec]:
    """Return extension specs for a target, sorted by priority then registration order."""
    specs = list(LIST_EXTENSION_REGISTRY.get(target_path, []))
    specs.sort(key=lambda s: (s.priority, s.module, s.class_name))
    return specs
