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
