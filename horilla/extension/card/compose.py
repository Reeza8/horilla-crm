"""
Compose HorillaCardView subclasses with extension mixins (_inherit_card).
"""

from __future__ import annotations

from types import new_class

from django.views.generic import View

from horilla.contrib.generics.views.card import HorillaCardView
from horilla.extension._super_rebind import rebind_namespace_supers
from horilla.extension.card.registry import CardExtensionSpec
from horilla.extension.list.merge import (
    merge_append_attr,
    merge_columns,
    merge_scalar_overrides,
)

_APPEND_SPEC_ATTRS = (
    ("bulk_update_fields_append", "bulk_update_fields"),
    ("export_exclude_append", "export_exclude"),
    ("exclude_columns_append", "exclude_columns"),
    ("actions_append", "actions"),
    ("custom_bulk_actions_append", "custom_bulk_actions"),
    ("additional_action_button_append", "additional_action_button"),
    ("exclude_quick_filter_fields_append", "exclude_quick_filter_fields"),
    ("exclude_columns_from_sorting_append", "exclude_columns_from_sorting"),
)

_LAYOUT_SKIP = frozenset(
    {
        "columns_insert",
        "columns_append",
        "bulk_update_fields_append",
        "export_exclude_append",
        "exclude_columns_append",
        "actions_append",
        "custom_bulk_actions_append",
        "additional_action_button_append",
        "exclude_quick_filter_fields_append",
        "exclude_columns_from_sorting_append",
    }
)


def _import_card_view_class(path: str) -> type:
    module_name, class_name = path.rsplit(".", 1)
    module = __import__(module_name, fromlist=[class_name])
    view_class = getattr(module, class_name)
    if not isinstance(view_class, type) or not issubclass(view_class, View):
        raise TypeError(f"{path!r} is not a Django View subclass")
    if not issubclass(view_class, HorillaCardView):
        raise TypeError(f"{path!r} must be a HorillaCardView subclass")
    if view_class is HorillaCardView:
        raise TypeError(
            f"{path!r} must be a concrete HorillaCardView subclass, not HorillaCardView"
        )
    return view_class


def _spec_to_mixin(spec: CardExtensionSpec) -> type:
    """Build a mixin from an extension spec (methods + optional setup hook)."""
    namespace = {
        key: value for key, value in spec.class_attrs.items() if key not in _LAYOUT_SKIP
    }
    mixin_name = f"{spec.class_name.lstrip('_')}Mixin"
    mixin = type(mixin_name, (), namespace)

    # Give every copied method a __class__ closure cell bound to THIS mixin,
    # so a plain super().<method>(...) written in the extension subclass
    # correctly chains to the next extension (or the target view) instead of
    # raising TypeError — see horilla.extension._super_rebind.
    rebind_namespace_supers(namespace, mixin)

    if "setup_card_view_extension" not in spec.class_attrs:

        def setup_card_view_extension(self):
            """Default no-op on extension mixins without a custom hook."""

        mixin.setup_card_view_extension = setup_card_view_extension
    return mixin


def compose_card_view_class(target_path: str, target: type | None = None) -> type:
    """
    Compose target HorillaCardView with registered extensions.

    MRO: Composed -> ExtN -> ... -> Ext1 -> Target -> ...
    """
    if getattr(target, "__horilla_card_composed__", False):
        return target

    from horilla.extension.card.registry import get_card_extensions_for

    target = target or _import_card_view_class(target_path)
    specs = get_card_extensions_for(target_path)
    if not specs:
        return target

    mixins = [_spec_to_mixin(spec) for spec in specs]

    namespace: dict = {}
    merged_columns = merge_columns(getattr(target, "columns", None), specs)
    if merged_columns is not None:
        namespace["columns"] = merged_columns

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

    composed.__horilla_card_composed__ = True
    composed.__horilla_card_path__ = target_path
    composed.__wrapped_card_view__ = target
    composed.__module__ = target.__module__
    composed.__qualname__ = f"{target.__qualname__}Extended"

    return composed
