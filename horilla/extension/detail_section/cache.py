"""
Resolver and bootstrap cache state for detail-section extensions.

Kept import-free of compose/bootstrap/resolve to avoid cyclic imports.
"""

from __future__ import annotations

import threading

RESOLVER_CACHE: dict[type, type] = {}
RESOLVER_LOCK = threading.Lock()
LAST_FINGERPRINT: tuple | None = None


def clear_resolver_cache() -> None:
    """Clear per-view-class resolution cache."""
    with RESOLVER_LOCK:
        RESOLVER_CACHE.clear()


def reset_bootstrap_fingerprint() -> None:
    """Force apply_detail_section_extensions to recompose on next resolve."""
    global LAST_FINGERPRINT
    LAST_FINGERPRINT = None


def invalidate_after_registry_change() -> None:
    """Invalidate caches when extensions register before full bootstrap."""
    reset_bootstrap_fingerprint()
    clear_resolver_cache()
