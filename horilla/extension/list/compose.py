"""
Compose HorillaListView subclasses with extension mixins (_inherit_list).
"""

from __future__ import annotations

from functools import cached_property
from types import new_class

from django.views.generic import View

from horilla.extension._super_rebind import rebind_namespace_supers
from horilla.extension.list.merge import (
    merge_append_attr,
    merge_columns,
    merge_scalar_overrides,
)
from horilla.extension.list.registry import ListExtensionSpec
from horilla.utils.functional import cached_property as django_cached_property


def _static_class_attr(target: type, name: str):
    """
    Return ``target``'s own class-level value for ``name``, or ``None`` when
    it is a descriptor (``cached_property``, ``property``, etc.) that only
    computes a real value on an instance.

    ``compose_list_view_class`` merges extension contributions (e.g.
    ``columns_insert``) onto the target's own static class attribute before
    composing — but a concrete list view found via base-class fallback (see
    ``horilla.extension.list.resolve._resolve_via_base_class``) may define
    ``columns``/``custom_bulk_actions``/etc. as a ``cached_property``
    instead of a plain list (it needs ``self.model``/``self.request`` to
    compute), and ``getattr(target, name)`` on the class itself returns the
    descriptor object, not a computed value. Skipping the merge for those
    leaves the target's own property to run normally on the composed
    subclass — extensions simply cannot statically insert into a
    dynamically computed list.
    """
    value = target.__dict__.get(name)
    if value is None:
        for ancestor in target.__mro__[1:]:
            if name in ancestor.__dict__:
                value = ancestor.__dict__[name]
                break
    if isinstance(value, (cached_property, django_cached_property, property)):
        return None
    return getattr(target, name, None)


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


def _import_list_view_class(path: str) -> type:
    module_name, class_name = path.rsplit(".", 1)
    module = __import__(module_name, fromlist=[class_name])
    view_class = getattr(module, class_name)
    if not isinstance(view_class, type) or not issubclass(view_class, View):
        raise TypeError(f"{path!r} is not a Django View subclass")
    return view_class


def _spec_to_mixin(spec: ListExtensionSpec) -> type:
    """Build a mixin from an extension spec (methods + optional setup hook)."""
    namespace = {}
    for key, value in spec.class_attrs.items():
        if key in (
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
        ):
            continue
        namespace[key] = value

    mixin_name = f"{spec.class_name.lstrip('_')}Mixin"
    mixin = type(mixin_name, (), namespace)

    # Give every copied method a __class__ closure cell bound to THIS mixin,
    # so a plain super().<method>(...) written in the extension subclass
    # correctly chains to the next extension (or the target view) instead of
    # raising TypeError — see horilla.extension._super_rebind.
    rebind_namespace_supers(namespace, mixin)

    if "setup_list_view_extension" not in spec.class_attrs:

        def setup_list_view_extension(self):
            """Default no-op on extension mixins without a custom hook."""

        mixin.setup_list_view_extension = setup_list_view_extension
    return mixin


def compose_list_view_class(target_path: str, target: type | None = None) -> type:
    """
    Compose target HorillaListView with registered extensions.

    MRO: Composed -> ExtN -> ... -> Ext1 -> Target -> ...
    """
    if getattr(target, "__horilla_list_composed__", False):
        return target

    from horilla.extension.list.registry import get_list_extensions_for

    target = target or _import_list_view_class(target_path)
    specs = get_list_extensions_for(target_path)
    if not specs:
        return target

    mixins = [_spec_to_mixin(spec) for spec in specs]

    namespace: dict = {}
    merged_columns = merge_columns(_static_class_attr(target, "columns"), specs)
    if merged_columns is not None:
        namespace["columns"] = merged_columns

    for spec_attr, target_attr in _APPEND_SPEC_ATTRS:
        merged = merge_append_attr(
            _static_class_attr(target, target_attr), specs, spec_attr
        )
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

    composed.__horilla_list_composed__ = True
    composed.__horilla_list_path__ = target_path
    composed.__wrapped_list_view__ = target
    composed.__module__ = target.__module__
    composed.__qualname__ = f"{target.__qualname__}Extended"

    return composed
