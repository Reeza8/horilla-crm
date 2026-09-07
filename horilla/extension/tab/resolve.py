"""
Resolve Tab view classes through _inherit_tab composition.
"""

from __future__ import annotations

from horilla.extension.tab import cache
from horilla.extension.tab.registry import TAB_COMPOSED_MAP


def _tab_view_path(view_class: type) -> str:
    return getattr(
        view_class,
        "__horilla_tab_path__",
        f"{view_class.__module__}.{view_class.__name__}",
    )


def _import_tab_view_class(path: str) -> type:
    module_name, class_name = path.rsplit(".", 1)
    module = __import__(module_name, fromlist=[class_name])
    return getattr(module, class_name)


def clear_tab_extension_cache() -> None:
    """Clear resolver cache (tests, autoreload)."""
    cache.invalidate_all()
    TAB_COMPOSED_MAP.clear()


def resolve_tab_view_class(view_class: type | str) -> type:
    """
    Return composed tab view class when extensions exist, else the original.

    Safe to call before apps are ready — returns the base class unchanged.
    """
    from horilla.extension.tab.bootstrap import apply_tab_extensions

    if isinstance(view_class, str):
        view_class = _import_tab_view_class(view_class)

    apply_tab_extensions()

    if view_class in cache.RESOLVER_CACHE:
        return cache.RESOLVER_CACHE[view_class]

    path = _tab_view_path(view_class)
    composed = TAB_COMPOSED_MAP.get(path)
    result = composed if composed is not None else view_class

    with cache.RESOLVER_LOCK:
        cache.RESOLVER_CACHE[view_class] = result
        if result is not view_class:
            cache.RESOLVER_CACHE[result] = result

    return result
