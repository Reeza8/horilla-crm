"""
Resolve DateTimeFormatter classes through _inherit_formatter composition.
"""

from __future__ import annotations

from horilla.extension.formatting import cache
from horilla.extension.formatting.registry import FORMATTER_COMPOSED_MAP

DEFAULT_FORMATTER_PATH = (
    "horilla.contrib.generics.formatting.datetime.DateTimeFormatter"
)


def _formatter_path(formatter_class: type) -> str:
    return getattr(
        formatter_class,
        "__horilla_formatter_path__",
        f"{formatter_class.__module__}.{formatter_class.__name__}",
    )


def _import_formatter_class(path: str) -> type:
    module_name, class_name = path.rsplit(".", 1)
    module = __import__(module_name, fromlist=[class_name])
    return getattr(module, class_name)


def clear_formatter_extension_cache() -> None:
    """Clear resolver/instance caches (tests, autoreload)."""
    cache.invalidate_all()
    FORMATTER_COMPOSED_MAP.clear()


def resolve_datetime_formatter_class(
    formatter_class: type | str | None = None,
) -> type:
    """
    Return composed formatter class when extensions exist, else the original.

    Safe to call before apps are ready — returns the base class unchanged.
    """
    from horilla.extension.formatting.bootstrap import apply_formatter_extensions

    if formatter_class is None:
        formatter_class = DEFAULT_FORMATTER_PATH

    if isinstance(formatter_class, str):
        formatter_class = _import_formatter_class(formatter_class)

    apply_formatter_extensions()

    if formatter_class in cache.RESOLVER_CACHE:
        return cache.RESOLVER_CACHE[formatter_class]

    path = _formatter_path(formatter_class)
    composed = FORMATTER_COMPOSED_MAP.get(path)
    result = composed if composed is not None else formatter_class

    with cache.RESOLVER_LOCK:
        cache.RESOLVER_CACHE[formatter_class] = result
        if result is not formatter_class:
            cache.RESOLVER_CACHE[result] = result

    return result


def get_datetime_formatter(formatter_class: type | str | None = None):
    """
    Return a cached formatter instance (composed when extensions are registered).
    """
    cls = resolve_datetime_formatter_class(formatter_class)
    with cache.RESOLVER_LOCK:
        instance = cache.INSTANCE_CACHE.get(cls)
        if instance is None:
            instance = cls()
            cache.INSTANCE_CACHE[cls] = instance
        return instance
