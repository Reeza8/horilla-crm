"""
Bootstrap _inherit_list composition after Django apps are loaded.
"""

from __future__ import annotations

import logging
import threading

from django.apps import apps as django_apps
from django.core.exceptions import AppRegistryNotReady

from horilla.extension.list import cache
from horilla.extension.list.compose import compose_list_view_class
from horilla.extension.list.registry import LIST_COMPOSED_MAP, LIST_EXTENSION_REGISTRY

logger = logging.getLogger(__name__)

_LOCK = threading.Lock()


def registry_fingerprint() -> tuple:
    """Fingerprint of registered list extensions (detect late-loaded extension apps)."""
    parts: list = []
    for path in sorted(LIST_EXTENSION_REGISTRY.keys()):
        for spec in LIST_EXTENSION_REGISTRY[path]:
            parts.append(
                (
                    path,
                    spec.module,
                    spec.class_name,
                    spec.priority,
                    tuple(spec.columns_insert),
                    tuple(spec.columns_append),
                    tuple(spec.bulk_update_fields_append),
                )
            )
    return tuple(parts)


def apply_list_extensions(force: bool = False) -> None:
    """
    Build composed list view classes for all registered _inherit_list targets.

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

        LIST_COMPOSED_MAP.clear()

        for target_path in sorted(LIST_EXTENSION_REGISTRY.keys()):
            try:
                composed = compose_list_view_class(target_path)
                if getattr(composed, "__horilla_list_composed__", False):
                    LIST_COMPOSED_MAP[target_path] = composed
            except Exception as exc:
                logger.exception(
                    "Failed to compose list extensions for %s: %s",
                    target_path,
                    exc,
                )
                raise

        cache.LAST_FINGERPRINT = fingerprint
        cache.clear_resolver_cache()


def _register_checks() -> None:
    import importlib

    importlib.import_module("horilla.extension.list.checks")


_register_checks()
