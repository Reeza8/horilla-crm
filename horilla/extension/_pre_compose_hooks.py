"""
Pre-compose hooks: run app-supplied discovery just before an
``apply_*_extensions()`` composes its registry.

Some extensions are not statically declared against one named target — they
are registered dynamically, once per model that opts in to a feature (see
``custom_fields/extensions.py``, ``detail_extensions.py``,
``filter_extensions.py``: one ``FormExtension``/``DetailExtension``/
``FilterExtension`` per model discovered via
``horilla.registry.feature.FEATURE_REGISTRY``). Which models have opted in
can change after this app's own ``ready()`` runs (a CRM app's
``registration.py`` may opt in later in ``INSTALLED_APPS`` order), so
discovery must re-run every time Horilla is about to compose that
extension type — the same moment ``apply_form_extensions()`` etc. already
runs, on every request until the registry stabilizes.

Before this module existed, achieving that meant reassigning the bootstrap
function itself (``forms_bootstrap.apply_form_extensions = wrapped``) — a
real monkey-patch on a Horilla module, even though it delegated to the real
extension classes underneath. This module replaces that with an ordinary
registration list any app can append to, and each ``apply_*_extensions()``
calls ``run_pre_compose_hooks(name)`` itself at the top of its own body —
no external module attribute is ever reassigned.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Callable

logger = logging.getLogger(__name__)

_HOOKS: dict[str, list[Callable[[], None]]] = defaultdict(list)


def register_pre_compose_hook(
    extension_type: str, callback: Callable[[], None]
) -> None:
    """
    Register ``callback`` to run before ``extension_type`` composes.

    ``extension_type`` matches the package name under ``horilla.extension``
    (``"forms"``, ``"filter"``, ``"detail"``, ``"detail_section"``, ...).
    ``callback`` takes no arguments and returns nothing — it should register
    extension classes (e.g. call ``type(..., (FormExtension,), namespace)``)
    as a side effect, the same way any ``FormExtension``/``FilterExtension``/
    etc. subclass registers itself at class-definition time. Safe to call
    more than once with the same callback only if the callback itself is
    idempotent (Horilla's own ``apply_*_extensions()`` functions already
    are).
    """
    if callback in _HOOKS[extension_type]:
        return
    _HOOKS[extension_type].append(callback)


def run_pre_compose_hooks(extension_type: str) -> None:
    """Run every hook registered for ``extension_type``, in registration order."""
    for callback in _HOOKS[extension_type]:
        try:
            callback()
        except Exception:
            logger.exception(
                "Pre-compose hook %r failed for extension type %r",
                getattr(callback, "__qualname__", callback),
                extension_type,
            )
            raise
