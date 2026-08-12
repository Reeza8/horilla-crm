"""
Registry for DateTimeFormatter extensions (_inherit_formatter).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# target formatter path -> ordered extension specs
FORMATTER_EXTENSION_REGISTRY: dict[str, list["FormatterExtensionSpec"]] = {}

# target formatter path -> composed formatter class
FORMATTER_COMPOSED_MAP: dict[str, type] = {}


@dataclass
class FormatterExtensionSpec:
    """Captured contribution from a DateTimeFormatterExtension subclass."""

    inherit_formatter: str
    class_name: str
    module: str
    extension_app_label: str
    priority: int = 0
    methods: dict[str, Any] = field(default_factory=dict)


def register_formatter_extension(spec: FormatterExtensionSpec) -> None:
    """Append an extension spec for a target formatter path."""
    FORMATTER_EXTENSION_REGISTRY.setdefault(spec.inherit_formatter, []).append(spec)


def get_formatter_extensions_for(target_path: str) -> list[FormatterExtensionSpec]:
    """Return specs for a target, sorted by priority then registration order."""
    specs = list(FORMATTER_EXTENSION_REGISTRY.get(target_path, []))
    specs.sort(key=lambda s: (s.priority, s.module, s.class_name))
    return specs
