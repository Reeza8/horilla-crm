"""
Bootstrap _inherit_detail composition after Django apps are loaded.
"""

from __future__ import annotations

import logging
import threading

from django.apps import apps as django_apps
from django.core.exceptions import AppRegistryNotReady

from horilla.extension.detail import cache
from horilla.extension.detail.compose import compose_detail_view_class
from horilla.extension.detail.registry import (
    DETAIL_COMPOSED_MAP,
    DETAIL_EXTENSION_REGISTRY,
)

logger = logging.getLogger(__name__)

_LOCK = threading.Lock()


def registry_fingerprint() -> tuple:
    """Fingerprint of registered detail extensions (detect late-loaded extension apps)."""
    parts: list = []
    for path in sorted(DETAIL_EXTENSION_REGISTRY.keys()):
        for spec in DETAIL_EXTENSION_REGISTRY[path]:
            parts.append(
                (
                    path,
                    spec.module,
                    spec.class_name,
                    spec.priority,
                    tuple(spec.body_insert),
                    tuple(spec.body_append),
                    tuple(spec.fieldsets_insert),
                    tuple(spec.header_fields_insert),
                    tuple(spec.actions_append),
                    tuple(spec.excluded_fields_append),
                )
            )
    return tuple(parts)


def apply_detail_extensions(force: bool = False) -> None:
    """
    Build composed detail view classes for all registered _inherit_detail targets.

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

        DETAIL_COMPOSED_MAP.clear()

        for target_path in sorted(DETAIL_EXTENSION_REGISTRY.keys()):
            try:
                composed = compose_detail_view_class(target_path)
                if getattr(composed, "__horilla_detail_composed__", False):
                    DETAIL_COMPOSED_MAP[target_path] = composed
            except Exception as exc:
                logger.exception(
                    "Failed to compose detail extensions for %s: %s",
                    target_path,
                    exc,
                )
                raise

        cache.LAST_FINGERPRINT = fingerprint
        cache.clear_resolver_cache()


def _register_checks() -> None:
    import importlib

    importlib.import_module("horilla.extension.detail.checks")


_register_checks()
