"""
Registry for Mixin extensions (_inherit_mixin).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# target path (module.ClassName or module.function_name) -> ordered extension specs
MIXIN_EXTENSION_REGISTRY: dict[str, list["MixinExtensionSpec"]] = {}

# target path -> set of id(spec) already applied (patched onto the target).
# Tracked per spec (not a single bool) so a newly registered extension on an
# already-patched target still gets applied instead of being silently
# skipped — see bootstrap.py.
MIXIN_APPLIED_MAP: dict[str, set[int]] = {}


@dataclass
class MixinExtensionSpec:
    """Captured contribution from a MixinExtension subclass."""

    inherit_mixin: str
    class_name: str
    module: str
    extension_app_label: str
    priority: int = 0
    methods: dict[str, Any] = field(default_factory=dict)


def register_mixin_extension(spec: MixinExtensionSpec) -> None:
    """Append an extension spec for a target path."""
    MIXIN_EXTENSION_REGISTRY.setdefault(spec.inherit_mixin, []).append(spec)
    from horilla.extension.mixin.cache import invalidate_all

    invalidate_all()


def get_mixin_extensions_for(target_path: str) -> list[MixinExtensionSpec]:
    """Return specs for a target, sorted by priority then registration order."""
    specs = list(MIXIN_EXTENSION_REGISTRY.get(target_path, []))
    specs.sort(key=lambda s: (s.priority, s.module, s.class_name))
    return specs
