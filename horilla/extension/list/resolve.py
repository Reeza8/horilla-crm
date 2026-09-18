"""
Resolve list view classes through _inherit_list composition.
"""

from __future__ import annotations

from horilla.extension.list import cache
from horilla.extension.list.registry import (
    LIST_BASE_COMPOSED_MAP,
    LIST_COMPOSED_MAP,
    LIST_EXTENSION_REGISTRY,
)


def _list_view_path(view_class: type) -> str:
    return getattr(
        view_class,
        "__horilla_list_path__",
        f"{view_class.__module__}.{view_class.__name__}",
    )


def _import_list_view_class(path: str) -> type:
    module_name, class_name = path.rsplit(".", 1)
    module = __import__(module_name, fromlist=[class_name])
    return getattr(module, class_name)


def clear_list_extension_cache() -> None:
    """Clear resolver cache (tests, autoreload)."""
    with cache.RESOLVER_LOCK:
        cache.RESOLVER_CACHE.clear()
        LIST_COMPOSED_MAP.clear()
        LIST_BASE_COMPOSED_MAP.clear()
    cache.reset_bootstrap_fingerprint()


def _resolve_via_base_class(view_class: type) -> type | None:
    """
    Fall back to a base class's ``_inherit_list`` registration.

    Lets one extension registered on a shared base (e.g.
    ``HorillaListView``) apply to every concrete subclass automatically,
    instead of requiring one registration per concrete list view. A
    concrete-class registration (checked first, in
    ``resolve_list_view_class``) always takes priority over this fallback.
    """
    from horilla.extension.list.compose import compose_list_view_class

    if view_class in LIST_BASE_COMPOSED_MAP:
        return LIST_BASE_COMPOSED_MAP[view_class]

    result = None
    for ancestor in view_class.__mro__[1:]:
        ancestor_path = _list_view_path(ancestor)
        if ancestor_path in LIST_EXTENSION_REGISTRY:
            result = compose_list_view_class(ancestor_path, target=view_class)
            break

    LIST_BASE_COMPOSED_MAP[view_class] = result
    return result


def resolve_list_view_class(view_class: type | str) -> type:
    """
    Return composed list view class when extensions exist, else the original.

    Checks an exact ``_inherit_list`` registration for ``view_class`` first,
    then falls back to a registration on any base class in its MRO (see
    ``_resolve_via_base_class``). Safe to call before apps are ready —
    returns the base class unchanged.
    """
    from horilla.extension.list.bootstrap import apply_list_extensions

    if isinstance(view_class, str):
        view_class = _import_list_view_class(view_class)

    apply_list_extensions()

    if view_class in cache.RESOLVER_CACHE:
        return cache.RESOLVER_CACHE[view_class]

    path = _list_view_path(view_class)
    composed = LIST_COMPOSED_MAP.get(path)
    if composed is None:
        composed = _resolve_via_base_class(view_class)
    result = composed if composed is not None else view_class

    with cache.RESOLVER_LOCK:
        cache.RESOLVER_CACHE[view_class] = result
        if result is not view_class:
            cache.RESOLVER_CACHE[result] = result

    return result


def get_resolved_list_view_path(view_class: type) -> str:
    """Stable path for the original target list view (pre-composition)."""
    resolved = resolve_list_view_class(view_class)
    return _list_view_path(resolved)
