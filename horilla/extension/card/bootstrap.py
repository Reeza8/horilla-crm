"""
Bootstrap _inherit_card composition after Django apps are loaded.
"""

from __future__ import annotations

import logging
import threading

from django.apps import apps as django_apps
from django.core.exceptions import AppRegistryNotReady

from horilla.extension.card import cache
from horilla.extension.card.compose import compose_card_view_class
from horilla.extension.card.registry import CARD_COMPOSED_MAP, CARD_EXTENSION_REGISTRY

logger = logging.getLogger(__name__)

_LOCK = threading.Lock()


def registry_fingerprint() -> tuple:
    """Fingerprint of registered card extensions (detect late-loaded extension apps)."""
    parts: list = []
    for path in sorted(CARD_EXTENSION_REGISTRY.keys()):
        for spec in CARD_EXTENSION_REGISTRY[path]:
            parts.append(
                (
                    path,
                    spec.module,
                    spec.class_name,
                    spec.priority,
                    tuple(spec.columns_insert),
                    tuple(spec.columns_append),
                )
            )
    return tuple(parts)


def apply_card_extensions(force: bool = False) -> None:
    """
    Build composed card view classes for all registered _inherit_card targets.

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

        CARD_COMPOSED_MAP.clear()

        for target_path in sorted(CARD_EXTENSION_REGISTRY.keys()):
            try:
                composed = compose_card_view_class(target_path)
                if getattr(composed, "__horilla_card_composed__", False):
                    CARD_COMPOSED_MAP[target_path] = composed
            except Exception as exc:
                logger.exception(
                    "Failed to compose card extensions for %s: %s",
                    target_path,
                    exc,
                )
                raise

        cache.LAST_FINGERPRINT = fingerprint
        cache.clear_resolver_cache()


def _register_checks() -> None:
    import importlib

    importlib.import_module("horilla.extension.card.checks")


_register_checks()
