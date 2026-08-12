"""
Bootstrap _inherit_form composition after Django apps are loaded.
"""

from __future__ import annotations

import logging
import threading

from django.apps import apps as django_apps
from django.core.exceptions import AppRegistryNotReady

from horilla.extension.forms import cache
from horilla.extension.forms.compose import compose_form_class
from horilla.extension.forms.registry import FORM_COMPOSED_MAP, FORM_EXTENSION_REGISTRY

logger = logging.getLogger(__name__)

_LOCK = threading.Lock()


def apply_form_extensions(force: bool = False) -> None:
    """
    Build composed form classes for all registered _inherit_form targets.

    Idempotent. No-op until Django apps are ready (extension modules may load later).
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

        FORM_COMPOSED_MAP.clear()

        for target_path in sorted(FORM_EXTENSION_REGISTRY.keys()):
            try:
                composed = compose_form_class(target_path)
                if composed is not None:
                    FORM_COMPOSED_MAP[target_path] = composed
            except Exception as exc:
                logger.exception(
                    "Failed to compose form extensions for %s: %s",
                    target_path,
                    exc,
                )
                raise

        cache.set_bootstrap_applied(True)
        cache.clear_resolver_cache()


def _register_checks() -> None:
    import importlib

    importlib.import_module("horilla.extension.forms.checks")


_register_checks()
