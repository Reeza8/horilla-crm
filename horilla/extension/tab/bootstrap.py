"""
Bootstrap Tab view composition after Django apps are loaded.
"""

from __future__ import annotations

import logging
import threading

from django.apps import apps as django_apps
from django.core.exceptions import AppRegistryNotReady

from horilla.extension.tab import cache
from horilla.extension.tab.compose import compose_tab_view_class
from horilla.extension.tab.registry import TAB_COMPOSED_MAP, TAB_EXTENSION_REGISTRY

logger = logging.getLogger(__name__)

_LOCK = threading.Lock()


def apply_tab_extensions(force: bool = False) -> None:
    """Build composed tab view classes for registered _inherit_tab targets."""
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

        TAB_COMPOSED_MAP.clear()

        for target_path in sorted(TAB_EXTENSION_REGISTRY.keys()):
            try:
                composed = compose_tab_view_class(target_path)
                if getattr(composed, "__horilla_tab_composed__", False):
                    TAB_COMPOSED_MAP[target_path] = composed
            except Exception as exc:
                logger.exception(
                    "Failed to compose tab extensions for %s: %s",
                    target_path,
                    exc,
                )
                raise

        cache.set_bootstrap_applied(True)
        cache.clear_resolver_cache()
