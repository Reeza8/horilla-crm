"""
Bootstrap View composition after Django apps are loaded.
"""

from __future__ import annotations

import logging
import threading

from django.apps import apps as django_apps
from django.core.exceptions import AppRegistryNotReady

from horilla.extension.view import cache
from horilla.extension.view.compose import compose_view_class
from horilla.extension.view.registry import VIEW_COMPOSED_MAP, VIEW_EXTENSION_REGISTRY

logger = logging.getLogger(__name__)

_LOCK = threading.Lock()


def apply_view_extensions(force: bool = False) -> None:
    """Build composed view classes for registered _inherit_view targets."""
    if cache.is_bootstrap_applied() and not force:
        return

    try:
        if not django_apps.ready:
            return
    except AppRegistryNotReady:
        return

    with _LOCK:
        if cache.is_bootstrap_applied() and not force:
            return

        VIEW_COMPOSED_MAP.clear()

        for target_path in sorted(VIEW_EXTENSION_REGISTRY.keys()):
            try:
                composed = compose_view_class(target_path)
                if getattr(composed, "__horilla_view_composed__", False):
                    VIEW_COMPOSED_MAP[target_path] = composed
            except Exception as exc:
                logger.exception(
                    "Failed to compose view extensions for %s: %s",
                    target_path,
                    exc,
                )
                raise

        cache.set_bootstrap_applied(True)
        cache.clear_resolver_cache()
