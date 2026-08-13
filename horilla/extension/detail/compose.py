"""
Compose HorillaDetailView subclasses with extension mixins (_inherit_detail).
"""

from __future__ import annotations

from types import new_class

from horilla.contrib.generics.views.details import HorillaDetailView
from horilla.extension.detail.merge import (
    merge_append_attr,
    merge_body,
    merge_fieldsets,
    merge_header_fields,
    merge_scalar_overrides,
)
from horilla.extension.detail.registry import DetailExtensionSpec

_APPEND_SPEC_ATTRS = (
    ("excluded_fields_append", "excluded_fields"),
    ("split_excluded_fields_append", "split_excluded_fields"),
    ("actions_append", "actions"),
    ("badge_append", "badge"),
    ("breadcrumbs_append", "breadcrumbs"),
)

_LAYOUT_SKIP = frozenset(
    {
        "body_insert",
        "body_append",
        "fieldsets_insert",
        "header_fields_insert",
        "header_fields_append",
        "excluded_fields_append",
        "split_excluded_fields_append",
        "actions_append",
        "badge_append",
        "breadcrumbs_append",
    }
)


def _import_detail_view_class(path: str) -> type:
    module_name, class_name = path.rsplit(".", 1)
    module = __import__(module_name, fromlist=[class_name])
    view_class = getattr(module, class_name)
    if not isinstance(view_class, type) or not issubclass(
        view_class, HorillaDetailView
    ):
        raise TypeError(f"{path!r} must be a HorillaDetailView subclass")
    if view_class is HorillaDetailView:
        raise TypeError(
            f"{path!r} must be a concrete HorillaDetailView subclass, not HorillaDetailView"
        )
    return view_class


def _register_detail_view_registry(composed: type, target: type) -> None:
    """Pipeline POST and field defaults resolve the view from _view_registry[model]."""
    model = getattr(composed, "model", None) or getattr(target, "model", None)
    if model is not None:
        HorillaDetailView._view_registry[model] = composed


def _spec_to_mixin(spec: DetailExtensionSpec) -> type:
    """Build a mixin from an extension spec (methods + optional setup hook)."""
    namespace = {
        key: value for key, value in spec.class_attrs.items() if key not in _LAYOUT_SKIP
    }

    mixin_name = f"{spec.class_name.lstrip('_')}Mixin"
    mixin = type(mixin_name, (), namespace)

    if "setup_detail_view_extension" not in spec.class_attrs:

        def setup_detail_view_extension(self):
            """Default no-op on extension mixins without a custom hook."""

        mixin.setup_detail_view_extension = setup_detail_view_extension
    return mixin


def compose_detail_view_class(target_path: str, target: type | None = None) -> type:
    """
    Compose target HorillaDetailView with registered extensions.

    MRO: Composed -> ExtN -> ... -> Ext1 -> Target -> ...
    """
    if getattr(target, "__horilla_detail_composed__", False):
        return target

    from horilla.extension.detail.registry import get_detail_extensions_for

    target = target or _import_detail_view_class(target_path)
    specs = get_detail_extensions_for(target_path)
    if not specs:
        _register_detail_view_registry(target, target)
        return target

    mixins = [_spec_to_mixin(spec) for spec in specs]

    namespace: dict = {}
    merged_body = merge_body(getattr(target, "body", None), specs)
    if merged_body is not None:
        namespace["body"] = merged_body

    merged_fieldsets = merge_fieldsets(getattr(target, "fieldsets", None), specs)
    if merged_fieldsets is not None:
        namespace["fieldsets"] = merged_fieldsets

    merged_header = merge_header_fields(getattr(target, "header_fields", None), specs)
    if merged_header is not None:
        namespace["header_fields"] = merged_header

    for spec_attr, target_attr in _APPEND_SPEC_ATTRS:
        merged = merge_append_attr(getattr(target, target_attr, None), specs, spec_attr)
        if merged is not None:
            namespace[target_attr] = merged

    namespace.update(merge_scalar_overrides(specs))

    composed_name = f"{target.__name__}Extended"
    bases = tuple(reversed(mixins)) + (target,)

    composed = new_class(
        composed_name,
        bases,
        {},
        lambda ns: ns.update(namespace),
    )

    composed.__horilla_detail_composed__ = True
    composed.__horilla_detail_path__ = target_path
    composed.__wrapped_detail_view__ = target
    composed.__module__ = target.__module__
    composed.__qualname__ = f"{target.__qualname__}Extended"

    _register_detail_view_registry(composed, target)

    return composed
