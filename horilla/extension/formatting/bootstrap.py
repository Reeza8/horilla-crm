"""
Bootstrap DateTimeFormatter composition after Django apps are loaded.
"""

from __future__ import annotations

import logging
import threading

from django.apps import apps as django_apps
from django.core.exceptions import AppRegistryNotReady

from horilla.extension.formatting import cache
from horilla.extension.formatting.compose import compose_formatter_class
from horilla.extension.formatting.registry import (
    FORMATTER_COMPOSED_MAP,
    FORMATTER_EXTENSION_REGISTRY,
)

logger = logging.getLogger(__name__)

_LOCK = threading.Lock()


def apply_formatter_extensions(force: bool = False) -> None:
    """
    Build composed formatter classes for all registered _inherit_formatter targets.

    Idempotent. No-op until Django apps are ready.
    """
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

        FORMATTER_COMPOSED_MAP.clear()

        for target_path in sorted(FORMATTER_EXTENSION_REGISTRY.keys()):
            try:
                composed = compose_formatter_class(target_path)
                if composed is not None:
                    FORMATTER_COMPOSED_MAP[target_path] = composed
            except Exception as exc:
                logger.exception(
                    "Failed to compose formatter extensions for %s: %s",
                    target_path,
                    exc,
                )
                raise

        cache.set_bootstrap_applied(True)
        cache.clear_resolver_cache()
