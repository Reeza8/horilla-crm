"""
Bootstrap cache for Mixin extensions (_inherit_mixin).
"""

from __future__ import annotations

import threading

_LOCK = threading.Lock()
_BOOTSTRAP_APPLIED = [False]


def is_bootstrap_applied() -> bool:
    """Return whether mixin extensions have been applied this process."""
    return _BOOTSTRAP_APPLIED[0]


def set_bootstrap_applied(applied: bool = True) -> None:
    """Record whether apply_mixin_extensions has completed."""
    _BOOTSTRAP_APPLIED[0] = applied


def reset_bootstrap_applied() -> None:
    """Force apply_mixin_extensions to re-apply on next call."""
    set_bootstrap_applied(False)


def invalidate_all() -> None:
    """Reset the bootstrap-applied flag (registry changed after startup)."""
    reset_bootstrap_applied()


def lock():
    return _LOCK
