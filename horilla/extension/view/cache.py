"""
Resolver/bootstrap cache for View extensions (_inherit_view).
"""

from __future__ import annotations

import threading

RESOLVER_CACHE: dict = {}
RESOLVER_LOCK = threading.Lock()
_BOOTSTRAP_APPLIED = [False]


def clear_resolver_cache() -> None:
    """Clear per-view-class resolution cache."""
    with RESOLVER_LOCK:
        RESOLVER_CACHE.clear()


def is_bootstrap_applied() -> bool:
    """Return whether view extensions have been composed this process."""
    return _BOOTSTRAP_APPLIED[0]


def set_bootstrap_applied(applied: bool = True) -> None:
    """Record whether apply_view_extensions has completed."""
    _BOOTSTRAP_APPLIED[0] = applied


def reset_bootstrap_applied() -> None:
    """Force apply_view_extensions to recompose on next resolve."""
    set_bootstrap_applied(False)


def invalidate_all() -> None:
    """Clear resolver cache and bootstrap applied flag."""
    clear_resolver_cache()
    reset_bootstrap_applied()
