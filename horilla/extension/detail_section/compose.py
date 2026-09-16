"""
Compose HorillaDetailSectionView subclasses with extension mixins (_inherit_detail_section).
"""

from __future__ import annotations

from types import new_class

from horilla.contrib.generics.views.detail_tabs import HorillaDetailSectionView
from horilla.extension._super_rebind import rebind_namespace_supers
from horilla.extension.detail_section.merge import merge_append_attr, merge_body
from horilla.extension.detail_section.registry import DetailSectionExtensionSpec

_APPEND_SPEC_ATTRS = (
    ("excluded_fields_append", "excluded_fields"),
    ("include_fields_append", "include_fields"),
)

_LAYOUT_SKIP = frozenset(
    {
        "body_insert",
        "body_append",
        "excluded_fields_append",
        "include_fields_append",
    }
)


def _import_detail_section_view_class(path: str) -> type:
    module_name, class_name = path.rsplit(".", 1)
    module = __import__(module_name, fromlist=[class_name])
    view_class = getattr(module, class_name)
    if not isinstance(view_class, type) or not issubclass(
        view_class, HorillaDetailSectionView
    ):
        raise TypeError(f"{path!r} must be a HorillaDetailSectionView subclass")
    if view_class is HorillaDetailSectionView:
        raise TypeError(
            f"{path!r} must be a concrete HorillaDetailSectionView subclass, "
            "not HorillaDetailSectionView"
        )
    return view_class


def _register_detail_section_view_registry(composed: type, target: type) -> None:
    """Selector defaults resolve the view from _view_registry[model] like details do."""
    model = getattr(composed, "model", None) or getattr(target, "model", None)
    if model is not None:
        HorillaDetailSectionView._view_registry[model] = composed


def _spec_to_mixin(spec: DetailSectionExtensionSpec) -> type:
    """Build a mixin from an extension spec (layout attrs + methods)."""
    namespace = {
        key: value for key, value in spec.class_attrs.items() if key not in _LAYOUT_SKIP
    }
    mixin_name = f"{spec.class_name.lstrip('_')}Mixin"
    mixin = type(mixin_name, (), namespace)

    # Give every copied method (get_context_data, or any other override an
    # extension declares) a __class__ closure cell bound to THIS mixin, so a
    # plain super().get_context_data(**kwargs) written in the
    # DetailSectionExtension subclass correctly chains to the next extension
    # (or the target view) instead of raising TypeError — see
    # horilla.extension._super_rebind.
    rebind_namespace_supers(namespace, mixin)
    return mixin


def compose_detail_section_view_class(
    target_path: str, target: type | None = None
) -> type:
    """
    Compose target HorillaDetailSectionView with registered extensions.

    MRO: Composed -> ExtN -> ... -> Ext1 -> Target -> ...
    """
    if getattr(target, "__horilla_detail_section_composed__", False):
        return target

    from horilla.extension.detail_section.registry import (
        get_detail_section_extensions_for,
    )

    target = target or _import_detail_section_view_class(target_path)
    specs = get_detail_section_extensions_for(target_path)
    if not specs:
        _register_detail_section_view_registry(target, target)
        return target

    mixins = [_spec_to_mixin(spec) for spec in specs]

    namespace: dict = {}
    merged_body = merge_body(getattr(target, "body", None), specs)
    if merged_body is not None:
        namespace["body"] = merged_body

    for spec_attr, target_attr in _APPEND_SPEC_ATTRS:
        merged = merge_append_attr(getattr(target, target_attr, None), specs, spec_attr)
        if merged is not None:
            namespace[target_attr] = merged

    composed_name = f"{target.__name__}Extended"
    bases = tuple(reversed(mixins)) + (target,)

    composed = new_class(
        composed_name,
        bases,
        {},
        lambda ns: ns.update(namespace),
    )

    composed.__horilla_detail_section_composed__ = True
    composed.__horilla_detail_section_path__ = target_path
    composed.__wrapped_detail_section_view__ = target
    composed.__module__ = target.__module__
    composed.__qualname__ = f"{target.__qualname__}Extended"

    _register_detail_section_view_registry(composed, target)

    return composed
