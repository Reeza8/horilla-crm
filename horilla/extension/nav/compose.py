"""
Compose HorillaNavView subclasses with extension mixins (_inherit_nav).
"""

from __future__ import annotations

from functools import cached_property
from types import new_class

from django.views.generic import View

from horilla.contrib.generics.views.navbar import HorillaNavView
from horilla.extension._super_rebind import rebind_namespace_supers
from horilla.extension.nav.merge import (
    merge_append_attr,
    merge_custom_view_type,
    merge_exclude_kanban_fields,
    merge_navbar_indication_attrs,
    merge_scalar_overrides,
)
from horilla.extension.nav.registry import NavExtensionSpec


def _import_nav_view_class(path: str) -> type:
    module_name, class_name = path.rsplit(".", 1)
    module = __import__(module_name, fromlist=[class_name])
    view_class = getattr(module, class_name)
    if not isinstance(view_class, type) or not issubclass(view_class, View):
        raise TypeError(f"{path!r} is not a Django View subclass")
    if not issubclass(view_class, HorillaNavView):
        raise TypeError(f"{path!r} must be a HorillaNavView subclass")
    if view_class is HorillaNavView:
        raise TypeError(
            f"{path!r} must be a concrete HorillaNavView subclass, not HorillaNavView"
        )
    return view_class


def _actions_append_from_specs(specs: list[NavExtensionSpec]) -> list:
    merged: list = []
    for spec in specs:
        merged.extend(spec.actions_append or [])
    return merged


def _build_actions_mixin(specs: list[NavExtensionSpec]) -> type | None:
    append = _actions_append_from_specs(specs)
    if not append:
        return None

    class _NavActionsMixin:
        @cached_property
        def actions(self):
            """Merge base nav actions with extension actions_append entries."""
            base_actions = list(super().actions)
            seen = {repr(a) if isinstance(a, dict) else a for a in base_actions}
            for action in append:
                key = repr(action) if isinstance(action, dict) else action
                if key not in seen:
                    seen.add(key)
                    base_actions.append(action)
            return base_actions

    return _NavActionsMixin


def _build_custom_view_type_mixin(specs: list[NavExtensionSpec]) -> type | None:
    updates: dict = {}
    for spec in specs:
        updates.update(spec.custom_view_type_update or {})
    if not updates:
        return None

    class _NavCustomViewTypeMixin:
        @cached_property
        def custom_view_type(self):
            """Merge base custom_view_type dict with extension updates."""
            try:
                base = super().custom_view_type
            except AttributeError:
                base = {}
            if not isinstance(base, dict):
                base = {}
            merged = dict(base)
            merged.update(updates)
            return merged

    return _NavCustomViewTypeMixin


def _spec_to_mixin(spec: NavExtensionSpec) -> type:
    """Build a mixin from an extension spec (methods only; layout merged on composed class)."""
    skip = frozenset(
        {
            "actions_append",
            "custom_view_type_update",
            "column_selector_exclude_fields_append",
            "exclude_kanban_fields_append",
            "navbar_indication_attrs_update",
        }
    )
    namespace = {
        key: value for key, value in spec.class_attrs.items() if key not in skip
    }
    mixin_name = f"{spec.class_name.lstrip('_')}Mixin"
    mixin = type(mixin_name, (), namespace)

    # Give every copied method a __class__ closure cell bound to THIS mixin,
    # so a plain super().<method>(...) written in the extension subclass
    # correctly chains to the next extension (or the target view) instead of
    # raising TypeError — see horilla.extension._super_rebind.
    rebind_namespace_supers(namespace, mixin)

    if "setup_nav_view_extension" not in spec.class_attrs:

        def setup_nav_view_extension(self):
            """Default no-op on extension mixins without a custom hook."""

        mixin.setup_nav_view_extension = setup_nav_view_extension
    return mixin


def compose_nav_view_class(target_path: str, target: type | None = None) -> type:
    """
    Compose target HorillaNavView with registered extensions.

    MRO: Composed -> ExtN -> ... -> Ext1 -> Target -> ...
    """
    if getattr(target, "__horilla_nav_composed__", False):
        return target

    from horilla.extension.nav.registry import get_nav_extensions_for

    target = target or _import_nav_view_class(target_path)
    specs = get_nav_extensions_for(target_path)
    if not specs:
        return target

    mixins: list[type] = [_spec_to_mixin(spec) for spec in specs]
    actions_mixin = _build_actions_mixin(specs)
    if actions_mixin is not None:
        mixins.append(actions_mixin)
    cvt_mixin = _build_custom_view_type_mixin(specs)
    if cvt_mixin is not None:
        mixins.append(cvt_mixin)

    namespace: dict = {}

    # Plain dict custom_view_type on the target class only (not @cached_property).
    raw_cvt = target.__dict__.get("custom_view_type")
    if isinstance(raw_cvt, dict) and cvt_mixin is None:
        merged_cvt = merge_custom_view_type(raw_cvt, specs)
        if merged_cvt is not None:
            namespace["custom_view_type"] = merged_cvt

    merged_cols = merge_append_attr(
        getattr(target, "column_selector_exclude_fields", None),
        specs,
        "column_selector_exclude_fields_append",
    )
    if merged_cols is not None:
        namespace["column_selector_exclude_fields"] = merged_cols

    merged_kanban = merge_exclude_kanban_fields(
        getattr(target, "exclude_kanban_fields", None), specs
    )
    if merged_kanban is not None:
        namespace["exclude_kanban_fields"] = merged_kanban

    base_indication = getattr(target, "navbar_indication_attrs", None)
    if not isinstance(base_indication, dict):
        base_indication = base_indication if base_indication else None
    merged_indication = merge_navbar_indication_attrs(base_indication, specs)
    if merged_indication is not None:
        namespace["navbar_indication_attrs"] = merged_indication

    namespace.update(merge_scalar_overrides(specs))

    composed_name = f"{target.__name__}Extended"
    bases = tuple(reversed(mixins)) + (target,)

    composed = new_class(
        composed_name,
        bases,
        {},
        lambda ns: ns.update(namespace),
    )

    composed.__horilla_nav_composed__ = True
    composed.__horilla_nav_path__ = target_path
    composed.__wrapped_nav_view__ = target
    composed.__module__ = target.__module__
    composed.__qualname__ = f"{target.__qualname__}Extended"

    return composed
