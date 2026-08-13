"""
Resolve View classes through _inherit_view composition.
"""

from __future__ import annotations

from horilla.extension.view import cache
from horilla.extension.view.registry import VIEW_COMPOSED_MAP


def _view_path(view_class: type) -> str:
    return getattr(
        view_class,
        "__horilla_view_path__",
        f"{view_class.__module__}.{view_class.__name__}",
    )


def _import_view_class(path: str) -> type:
    module_name, class_name = path.rsplit(".", 1)
    module = __import__(module_name, fromlist=[class_name])
    return getattr(module, class_name)


def clear_view_extension_cache() -> None:
    """Clear resolver cache (tests, autoreload)."""
    cache.invalidate_all()
    VIEW_COMPOSED_MAP.clear()


def resolve_view_class(view_class: type | str) -> type:
    """
    Return composed view class when extensions exist, else the original.

    Safe to call before apps are ready — returns the base class unchanged.
    """
    from horilla.extension.view.bootstrap import apply_view_extensions

    if isinstance(view_class, str):
        view_class = _import_view_class(view_class)

    apply_view_extensions()

    if view_class in cache.RESOLVER_CACHE:
        return cache.RESOLVER_CACHE[view_class]

    path = _view_path(view_class)
    composed = VIEW_COMPOSED_MAP.get(path)
    result = composed if composed is not None else view_class

    with cache.RESOLVER_LOCK:
        cache.RESOLVER_CACHE[view_class] = result
        if result is not view_class:
            cache.RESOLVER_CACHE[result] = result

    return result
