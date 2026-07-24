"""
Bootstrap _inherit_nav composition after Django apps are loaded.
"""

from __future__ import annotations

import logging
import threading

from django.apps import apps as django_apps
from django.core.exceptions import AppRegistryNotReady

from horilla.extension.nav import cache
from horilla.extension.nav.compose import compose_nav_view_class
from horilla.extension.nav.registry import NAV_COMPOSED_MAP, NAV_EXTENSION_REGISTRY

logger = logging.getLogger(__name__)

_LOCK = threading.Lock()


def registry_fingerprint() -> tuple:
    """Fingerprint of registered nav extensions (detect late-loaded extension apps)."""
    parts: list = []
    for path in sorted(NAV_EXTENSION_REGISTRY.keys()):
        for spec in NAV_EXTENSION_REGISTRY[path]:
            parts.append(
                (
                    path,
                    spec.module,
                    spec.class_name,
                    spec.priority,
                    tuple(spec.actions_append),
                    tuple(sorted((spec.custom_view_type_update or {}).keys())),
                )
            )
    return tuple(parts)


def apply_nav_extensions(force: bool = False) -> None:
    """
    Build composed nav view classes for all registered _inherit_nav targets.

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

        NAV_COMPOSED_MAP.clear()

        for target_path in sorted(NAV_EXTENSION_REGISTRY.keys()):
            try:
                composed = compose_nav_view_class(target_path)
                if getattr(composed, "__horilla_nav_composed__", False):
                    NAV_COMPOSED_MAP[target_path] = composed
            except Exception as exc:
                logger.exception(
                    "Failed to compose nav extensions for %s: %s",
                    target_path,
                    exc,
                )
                raise

        cache.LAST_FINGERPRINT = fingerprint
        cache.clear_resolver_cache()


def _register_checks() -> None:
    import importlib

    importlib.import_module("horilla.extension.nav.checks")


_register_checks()
