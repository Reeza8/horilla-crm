"""
Registry for View extensions (_inherit_view).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# target view path -> ordered extension specs
VIEW_EXTENSION_REGISTRY: dict[str, list["ViewExtensionSpec"]] = {}

# target view path -> composed view class
VIEW_COMPOSED_MAP: dict[str, type] = {}

# concrete view class -> composed subclass, resolved lazily when the
# extension is registered on a base class rather than the concrete view
# itself (see horilla.extension.view.resolve._resolve_via_base_class).
# Keyed by class object, not path, since these are discovered on demand
# rather than enumerated from VIEW_EXTENSION_REGISTRY.
VIEW_BASE_COMPOSED_MAP: dict[type, type | None] = {}


@dataclass
class ViewExtensionSpec:
    """Captured contribution from a ViewExtension subclass."""

    inherit_view: str
    class_name: str
    module: str
    extension_app_label: str
    priority: int = 0
    methods: dict[str, Any] = field(default_factory=dict)


def register_view_extension(spec: ViewExtensionSpec) -> None:
    """Append an extension spec for a target view path."""
    VIEW_EXTENSION_REGISTRY.setdefault(spec.inherit_view, []).append(spec)
    from horilla.extension.view.cache import invalidate_all

    invalidate_all()


def get_view_extensions_for(target_path: str) -> list[ViewExtensionSpec]:
    """Return specs for a target, sorted by priority then registration order."""
    specs = list(VIEW_EXTENSION_REGISTRY.get(target_path, []))
    specs.sort(key=lambda s: (s.priority, s.module, s.class_name))
    return specs
