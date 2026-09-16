"""
Compose DateTimeFormatter with extension mixins (_inherit_formatter).
"""

from __future__ import annotations

from types import new_class

from horilla.extension._super_rebind import rebind_namespace_supers
from horilla.extension.formatting.registry import (
    FormatterExtensionSpec,
    get_formatter_extensions_for,
)


def _import_formatter_class(path: str) -> type:
    module_name, class_name = path.rsplit(".", 1)
    module = __import__(module_name, fromlist=[class_name])
    return getattr(module, class_name)


def _spec_to_mixin(spec: FormatterExtensionSpec) -> type:
    """
    Build a mixin from extension method overrides.

    Zero-arg ``super()`` inside a registration-class method now works: each
    copied method's ``__class__`` closure cell is rebound to this mixin (see
    horilla.extension._super_rebind), so ``super().format_date(self, ...)``
    correctly chains to the next extension or the target formatter — calling
    the target base explicitly (e.g. ``DateTimeFormatter.format_date(self,
    ...)``) is no longer required, though it still works for a single
    registered extension.
    """
    mixin_name = f"{spec.class_name.lstrip('_')}Mixin"
    namespace = dict(spec.methods)
    mixin = type(mixin_name, (), namespace)
    rebind_namespace_supers(namespace, mixin)
    return mixin


def compose_formatter_class(target_path: str, target: type | None = None) -> type:
    """
    Compose target formatter with registered extensions.

    MRO: Composed -> ExtN -> ... -> Ext1 -> Target
    """
    if getattr(target, "__horilla_formatter_composed__", False):
        return target

    target = target or _import_formatter_class(target_path)
    specs = get_formatter_extensions_for(target_path)
    if not specs:
        return target

    mixins = [_spec_to_mixin(spec) for spec in specs]
    composed_name = f"{target.__name__}Extended"
    bases = tuple(reversed(mixins)) + (target,)

    composed = new_class(composed_name, bases, {}, lambda ns: None)

    composed.__horilla_formatter_composed__ = True
    composed.__horilla_formatter_path__ = target_path
    composed.__wrapped_formatter__ = target
    composed.__module__ = target.__module__
    composed.__qualname__ = f"{target.__qualname__}Extended"
    return composed
