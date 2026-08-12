"""
Compose DateTimeFormatter with extension mixins (_inherit_formatter).
"""

from __future__ import annotations

from types import new_class

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

    Note: zero-arg ``super()`` inside registration-class methods keeps a fixed
    ``__class__`` cell and will break on the composed type. Extensions should
    call the target base explicitly, e.g.
    ``DateTimeFormatter.format_date(self, ...)``.
    """
    mixin_name = f"{spec.class_name.lstrip('_')}Mixin"
    return type(mixin_name, (), dict(spec.methods))


def compose_formatter_class(
    target_path: str, target: type | None = None
) -> type:
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
