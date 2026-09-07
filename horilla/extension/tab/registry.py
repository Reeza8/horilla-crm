"""
Registry for Tab view extensions (_inherit_tab).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# target tab view path -> ordered extension specs
TAB_EXTENSION_REGISTRY: dict[str, list["TabExtensionSpec"]] = {}

# target tab view path -> composed view class
TAB_COMPOSED_MAP: dict[str, type] = {}


@dataclass
class TabExtensionSpec:
    """Captured contribution from a TabExtension subclass."""

    inherit_tab: str
    class_name: str
    module: str
    extension_app_label: str
    priority: int = 0
    methods: dict[str, Any] = field(default_factory=dict)


def register_tab_extension(spec: TabExtensionSpec) -> None:
    """Append an extension spec for a target tab view path."""
    TAB_EXTENSION_REGISTRY.setdefault(spec.inherit_tab, []).append(spec)
    from horilla.extension.tab.cache import invalidate_all

    invalidate_all()


def get_tab_extensions_for(target_path: str) -> list[TabExtensionSpec]:
    """Return specs for a target, sorted by priority then registration order."""
    specs = list(TAB_EXTENSION_REGISTRY.get(target_path, []))
    specs.sort(key=lambda s: (s.priority, s.module, s.class_name))
    return specs
