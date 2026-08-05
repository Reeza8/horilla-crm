"""
Horilla functional - re-exports django.utils.functional for consistent imports.

Use: from horilla.utils.functional import cached_property
     from horilla.utils.functional import lazy, Promise, ...
"""

from django.utils.functional import (
    LazyObject,
    Promise,
    SimpleLazyObject,
    cached_property,
    classproperty,
    empty,
    keep_lazy,
    keep_lazy_text,
    lazy,
    lazystr,
    partition,
)

__all__ = [
    "LazyObject",
    "Promise",
    "SimpleLazyObject",
    "cached_property",
    "classproperty",
    "empty",
    "keep_lazy",
    "keep_lazy_text",
    "lazy",
    "lazystr",
    "partition",
]
