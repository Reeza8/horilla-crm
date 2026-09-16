"""
Compose HorillaKanbanView subclasses with extension mixins (_inherit_kanban).
"""

from __future__ import annotations

from types import new_class

from horilla.contrib.generics.views.kanban import HorillaKanbanView
from horilla.extension._super_rebind import rebind_namespace_supers
from horilla.extension.kanban.merge import merge_exclude_kanban_fields
from horilla.extension.kanban.registry import KanbanExtensionSpec
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


def _import_kanban_view_class(path: str) -> type:
    module_name, class_name = path.rsplit(".", 1)
    module = __import__(module_name, fromlist=[class_name])
    view_class = getattr(module, class_name)
    if not isinstance(view_class, type) or not issubclass(
        view_class, HorillaKanbanView
    ):
        raise TypeError(f"{path!r} must be a HorillaKanbanView subclass")
    if view_class is HorillaKanbanView:
        raise TypeError(
            f"{path!r} must be a concrete HorillaKanbanView subclass, not HorillaKanbanView"
        )
    return view_class


def _register_kanban_view_registry(composed: type, target: type) -> None:
    """Drag-drop POST resolves the view from _view_registry[model]."""
    model = getattr(composed, "model", None) or getattr(target, "model", None)
    if model is not None:
        HorillaKanbanView._view_registry[model] = composed


def _spec_to_mixin(spec: KanbanExtensionSpec) -> type:
    """Build a mixin from an extension spec (methods + optional setup hook)."""
    skip_layout = {
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
        "exclude_kanban_fields_append",
    }
    namespace = {
        key: value for key, value in spec.class_attrs.items() if key not in skip_layout
    }

    mixin_name = f"{spec.class_name.lstrip('_')}Mixin"
    mixin = type(mixin_name, (), namespace)

    # Give every copied method a __class__ closure cell bound to THIS mixin,
    # so a plain super().<method>(...) written in the extension subclass
    # correctly chains to the next extension (or the target view) instead of
    # raising TypeError — see horilla.extension._super_rebind.
    rebind_namespace_supers(namespace, mixin)

    if "setup_kanban_view_extension" not in spec.class_attrs:

        def setup_kanban_view_extension(self):
            """Default no-op on extension mixins without a custom hook."""

        mixin.setup_kanban_view_extension = setup_kanban_view_extension
    return mixin


def compose_kanban_view_class(target_path: str, target: type | None = None) -> type:
    """
    Compose target HorillaKanbanView with registered extensions.

    MRO: Composed -> ExtN -> ... -> Ext1 -> Target -> ...
    """
    if getattr(target, "__horilla_kanban_composed__", False):
        return target

    from horilla.extension.kanban.registry import get_kanban_extensions_for

    target = target or _import_kanban_view_class(target_path)
    specs = get_kanban_extensions_for(target_path)
    if not specs:
        _register_kanban_view_registry(target, target)
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

    merged_exclude = merge_exclude_kanban_fields(
        getattr(target, "exclude_kanban_fields", None), specs
    )
    if merged_exclude is not None:
        namespace["exclude_kanban_fields"] = merged_exclude

    namespace.update(merge_scalar_overrides(specs))

    composed_name = f"{target.__name__}Extended"
    bases = tuple(reversed(mixins)) + (target,)

    composed = new_class(
        composed_name,
        bases,
        {},
        lambda ns: ns.update(namespace),
    )

    composed.__horilla_kanban_composed__ = True
    composed.__horilla_kanban_path__ = target_path
    composed.__wrapped_kanban_view__ = target
    composed.__module__ = target.__module__
    composed.__qualname__ = f"{target.__qualname__}Extended"

    _register_kanban_view_registry(composed, target)

    return composed
