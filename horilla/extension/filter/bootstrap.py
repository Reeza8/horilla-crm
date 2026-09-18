"""
Bootstrap _inherit_filter composition after Django apps are loaded.
"""

from __future__ import annotations

import logging
import threading

from django.apps import apps as django_apps
from django.core.exceptions import AppRegistryNotReady

from horilla.extension._pre_compose_hooks import run_pre_compose_hooks
from horilla.extension.filter import cache
from horilla.extension.filter.compose import compose_filterset_class
from horilla.extension.filter.registry import (
    FILTER_COMPOSED_MAP,
    FILTER_EXTENSION_REGISTRY,
)

logger = logging.getLogger(__name__)

_LOCK = threading.Lock()


def apply_filter_extensions(force: bool = False) -> None:
    """
    Build composed filterset classes for all registered _inherit_filter targets.

    Idempotent. No-op until Django apps are ready.

    Runs any registered pre-compose hooks first (see
    ``horilla.extension._pre_compose_hooks``) — apps that discover their
    extension targets dynamically register a hook instead of reassigning
    this function.
    """
    run_pre_compose_hooks("filter")

    if cache.BOOTSTRAP_APPLIED and not force:
        return

    try:
        if not django_apps.ready:
            return
    except AppRegistryNotReady:
        return

    with _LOCK:
        if cache.BOOTSTRAP_APPLIED and not force:
            return

        FILTER_COMPOSED_MAP.clear()

        for target_path in sorted(FILTER_EXTENSION_REGISTRY.keys()):
            try:
                composed = compose_filterset_class(target_path)
                if composed is not None:
                    FILTER_COMPOSED_MAP[target_path] = composed
            except Exception as exc:
                logger.exception(
                    "Failed to compose filter extensions for %s: %s",
                    target_path,
                    exc,
                )
                raise

        cache.BOOTSTRAP_APPLIED = True
        cache.clear_resolver_cache()


def _register_checks() -> None:
    import importlib

    importlib.import_module("horilla.extension.filter.checks")


_register_checks()
