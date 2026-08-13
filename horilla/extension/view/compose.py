"""
Compose View subclasses with extension mixins (_inherit_view).
"""

from __future__ import annotations

from types import new_class

from django.views.generic import View as DjangoView

from horilla.extension.view.registry import ViewExtensionSpec, get_view_extensions_for


def _import_view_class(path: str) -> type:
    module_name, class_name = path.rsplit(".", 1)
    module = __import__(module_name, fromlist=[class_name])
    view_class = getattr(module, class_name)
    if not isinstance(view_class, type) or not issubclass(view_class, DjangoView):
        raise TypeError(f"{path!r} is not a Django View subclass")
    return view_class


def _spec_to_mixin(spec: ViewExtensionSpec) -> type:
    """
    Build a mixin from extension method overrides.

    Note: zero-arg ``super()`` inside registration-class methods keeps a fixed
    ``__class__`` cell and will break on the composed type. Extensions should
    call the target base explicitly, e.g.
    ``EditFieldView.get_field_info(self, ...)``.
    """
    mixin_name = f"{spec.class_name.lstrip('_')}Mixin"
    return type(mixin_name, (), dict(spec.methods))


def compose_view_class(target_path: str, target: type | None = None) -> type:
    """
    Compose target view with registered extensions.

    MRO: Composed -> ExtN -> ... -> Ext1 -> Target
    """
    if getattr(target, "__horilla_view_composed__", False):
        return target

    target = target or _import_view_class(target_path)
    specs = get_view_extensions_for(target_path)
    if not specs:
        return target

    mixins = [_spec_to_mixin(spec) for spec in specs]
    composed_name = f"{target.__name__}Extended"
    bases = tuple(reversed(mixins)) + (target,)

    composed = new_class(composed_name, bases, {}, lambda ns: None)

    composed.__horilla_view_composed__ = True
    composed.__horilla_view_path__ = target_path
    composed.__wrapped_view__ = target
    composed.__module__ = target.__module__
    composed.__qualname__ = f"{target.__qualname__}Extended"
    return composed
