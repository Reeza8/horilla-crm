"""
Bootstrap Mixin extension application after Django apps are loaded.
"""

from __future__ import annotations

import logging

from django.apps import apps as django_apps
from django.core.exceptions import AppRegistryNotReady

from horilla.extension.mixin import cache
from horilla.extension.mixin.compose import apply_mixin_extension
from horilla.extension.mixin.registry import MIXIN_APPLIED_MAP, MIXIN_EXTENSION_REGISTRY

logger = logging.getLogger(__name__)


def apply_mixin_extensions(force: bool = False) -> None:
    """
    Apply newly registered ``_inherit_mixin`` extensions onto their targets.

    Every other ``apply_*_extensions()`` rebuilds a *new* composed class
    from scratch on each call, so re-running is always safe and ``force``
    means "recompute now." This package instead patches a *live* class or
    module attribute directly (see ``compose.py`` — there is no per-request
    resolution point to rebuild), so re-applying a target that is already
    applied would wrap the same method around itself a second time.
    ``force`` is accepted only for interface parity with the other
    ``apply_*_extensions()`` functions (``bootstrap_extensions()`` calls all
    of them uniformly) — it does not force a re-apply. Instead, each target
    tracks exactly which specs have already been applied
    (``MIXIN_APPLIED_MAP[target_path]``, a set of spec identities) so newly
    registered specs for an already-patched target are still picked up.
    """
    try:
        if not django_apps.ready:
            return
    except AppRegistryNotReady:
        return

    with cache.lock():
        for target_path in sorted(MIXIN_EXTENSION_REGISTRY.keys()):
            specs = MIXIN_EXTENSION_REGISTRY[target_path]
            applied_specs = MIXIN_APPLIED_MAP.setdefault(target_path, set())
            new_specs = [spec for spec in specs if id(spec) not in applied_specs]
            if not new_specs:
                continue
            try:
                apply_mixin_extension(target_path, new_specs)
                applied_specs.update(id(spec) for spec in new_specs)
            except Exception as exc:
                logger.exception(
                    "Failed to apply mixin extensions for %s: %s",
                    target_path,
                    exc,
                )
                raise

        cache.set_bootstrap_applied(True)


def _register_checks() -> None:
    import importlib

    importlib.import_module("horilla.extension.mixin.checks")


_register_checks()
