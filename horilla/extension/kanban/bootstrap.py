"""
Bootstrap _inherit_kanban composition after Django apps are loaded.
"""

from __future__ import annotations

import logging
import threading

from django.apps import apps as django_apps
from django.core.exceptions import AppRegistryNotReady

from horilla.extension.kanban import cache
from horilla.extension.kanban.compose import compose_kanban_view_class
from horilla.extension.kanban.registry import (
    KANBAN_COMPOSED_MAP,
    KANBAN_EXTENSION_REGISTRY,
)

logger = logging.getLogger(__name__)

_LOCK = threading.Lock()


def registry_fingerprint() -> tuple:
    """Fingerprint of registered kanban extensions (detect late-loaded extension apps)."""
    parts: list = []
    for path in sorted(KANBAN_EXTENSION_REGISTRY.keys()):
        for spec in KANBAN_EXTENSION_REGISTRY[path]:
            parts.append(
                (
                    path,
                    spec.module,
                    spec.class_name,
                    spec.priority,
                    tuple(spec.columns_insert),
                    tuple(spec.columns_append),
                    tuple(spec.exclude_kanban_fields_append),
                    tuple(spec.actions_append),
                )
            )
    return tuple(parts)


def apply_kanban_extensions(force: bool = False) -> None:
    """
    Build composed kanban view classes for all registered _inherit_kanban targets.

    Re-runs when the extension registry changes (e.g. extension app loads after the host application).
    """
    try:
        if not django_apps.ready:
            return
    except AppRegistryNotReady:
        return

    fingerprint = registry_fingerprint()
    if not force and fingerprint == cache.LAST_FINGERPRINT:
        return

    with _LOCK:
        if not force and fingerprint == cache.LAST_FINGERPRINT:
            return

        KANBAN_COMPOSED_MAP.clear()

        for target_path in sorted(KANBAN_EXTENSION_REGISTRY.keys()):
            try:
                composed = compose_kanban_view_class(target_path)
                if getattr(composed, "__horilla_kanban_composed__", False):
                    KANBAN_COMPOSED_MAP[target_path] = composed
            except Exception as exc:
                logger.exception(
                    "Failed to compose kanban extensions for %s: %s",
                    target_path,
                    exc,
                )
                raise

        cache.LAST_FINGERPRINT = fingerprint
        cache.clear_resolver_cache()


def _register_checks() -> None:
    import importlib

    importlib.import_module("horilla.extension.kanban.checks")


_register_checks()
