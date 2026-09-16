"""
Compose HorillaFilterSet subclasses with extension mixins (_inherit_filter).
"""

from __future__ import annotations

from types import new_class

import django_filters

from horilla.extension._super_rebind import rebind_namespace_supers
from horilla.extension.filter.registry import (
    FilterExtensionSpec,
    get_filter_extensions_for,
)


def _import_filterset_class(path: str) -> type:
    module_name, class_name = path.rsplit(".", 1)
    module = __import__(module_name, fromlist=[class_name])
    filterset_class = getattr(module, class_name)
    if not isinstance(filterset_class, type) or not issubclass(
        filterset_class, django_filters.FilterSet
    ):
        raise TypeError(f"{path!r} is not a django_filters.FilterSet subclass")
    return filterset_class


def _union_sequence(*sequences):
    seen = set()
    result = []
    for seq in sequences:
        for item in seq or []:
            if item not in seen:
                seen.add(item)
                result.append(item)
    return result


def _merge_search_fields(target: type, specs: list[FilterExtensionSpec]) -> list | None:
    target_meta = getattr(target, "Meta", None)
    base = list(getattr(target_meta, "search_fields", None) or [])
    if not base and not any(
        s.search_fields_insert or s.search_fields_append for s in specs
    ):
        if not any(s.meta_attrs.get("search_fields") for s in specs):
            return None

    merged = list(base)
    for spec in specs:
        meta_search = spec.meta_attrs.get("search_fields")
        if meta_search:
            merged = _union_sequence(merged, meta_search)
        for after, new_field in spec.search_fields_insert:
            if new_field in merged:
                continue
            if after in merged:
                merged.insert(merged.index(after) + 1, new_field)
            else:
                merged.append(new_field)
        for new_field in spec.search_fields_append:
            if new_field not in merged:
                merged.append(new_field)
    return merged


def _merge_meta(target: type, specs: list[FilterExtensionSpec]) -> type | None:
    """Build merged inner Meta class for the composed filterset."""
    target_meta = getattr(target, "Meta", None)
    if target_meta is None:
        if not specs or not any(s.meta_attrs for s in specs):
            return None
        target_meta = type("Meta", (), {})

    attrs = {}
    for key in ("model",):
        if hasattr(target_meta, key):
            attrs[key] = getattr(target_meta, key)

    exclude = list(getattr(target_meta, "exclude", None) or [])
    search_fields = list(getattr(target_meta, "search_fields", None) or [])
    fields_value = getattr(target_meta, "fields", None)
    name_split_fields = getattr(target_meta, "name_split_fields", None)

    for spec in specs:
        meta = spec.meta_attrs
        exclude = _union_sequence(exclude, meta.get("exclude"))
        exclude = _union_sequence(exclude, spec.exclude_append)
        search_fields = _union_sequence(search_fields, meta.get("search_fields"))
        if meta.get("name_split_fields") is not None:
            name_split_fields = meta.get("name_split_fields")
        fields_append = _union_sequence(
            list(spec.fields_append), meta.get("fields_append")
        )
        if fields_append and fields_value not in (None, "__all__"):
            if isinstance(fields_value, (list, tuple)):
                fields_value = tuple(_union_sequence(list(fields_value), fields_append))
            elif fields_value is None:
                fields_value = tuple(fields_append)

    merged_search = _merge_search_fields(target, specs)
    if merged_search is not None:
        search_fields = merged_search

    if exclude:
        attrs["exclude"] = tuple(exclude)
    if search_fields:
        attrs["search_fields"] = tuple(search_fields)
    if fields_value is not None:
        attrs["fields"] = fields_value
    if name_split_fields is not None:
        attrs["name_split_fields"] = name_split_fields

    return type("Meta", (), attrs)


def _collect_declared_filters(specs: list[FilterExtensionSpec]) -> dict:
    collected = {}
    for spec in specs:
        for name, filt in spec.declared_filters.items():
            if name in collected and name not in spec.override_filters:
                raise ValueError(
                    f"Duplicate declared filter {name!r} on {spec.inherit_filter} "
                    f"from {spec.module}.{spec.class_name}"
                )
            collected[name] = filt
    return collected


def _spec_to_mixin(spec: FilterExtensionSpec) -> type:
    namespace = dict(spec.class_attrs)
    mixin_name = f"{spec.class_name.lstrip('_')}Mixin"

    if "setup_filter_extension" not in namespace:

        def setup_filter_extension(self):
            """Default no-op; extension may override on the registration class."""

        namespace["setup_filter_extension"] = setup_filter_extension

    mixin = type(mixin_name, (), namespace)

    # Give every copied method a __class__ closure cell bound to THIS mixin,
    # so a plain super().<method>(...) written in the extension subclass
    # correctly chains to the next extension (or the target) instead of
    # raising TypeError — see horilla.extension._super_rebind.
    rebind_namespace_supers(namespace, mixin)

    # Call THIS mixin's own setup_filter_extension directly (closed over
    # here), not self.setup_filter_extension(). When two or more extensions
    # target the same filterset, every mixin's generated __init__ runs (each
    # chains to the next via super(mixin, self)), but a self.-resolved call
    # always finds only the first mixin's hook in the MRO — every other
    # extension's hook would silently never run. Reading the (already
    # rebound) function back off the mixin makes each extension's own hook
    # run exactly once, regardless of how many other extensions also target
    # this filterset.
    own_setup_filter_extension = mixin.__dict__["setup_filter_extension"]

    def __init__(self, *args, **kwargs):
        super(mixin, self).__init__(*args, **kwargs)
        own_setup_filter_extension(self)

    mixin.__init__ = __init__
    return mixin


def compose_filterset_class(target_path: str, target: type | None = None) -> type:
    """
    Compose target FilterSet with registered extensions.

    MRO: Composed -> ExtN -> ... -> Ext1 -> Target -> ...
    """
    if getattr(target, "__horilla_composed__", False):
        return target

    target = target or _import_filterset_class(target_path)
    specs = get_filter_extensions_for(target_path)
    if not specs:
        return target

    mixins = [_spec_to_mixin(spec) for spec in specs]
    declared = _collect_declared_filters(specs)
    meta = _merge_meta(target, specs)

    namespace = dict(declared)
    if meta is not None:
        namespace["Meta"] = meta

    composed_name = f"{target.__name__}Extended"
    bases = tuple(reversed(mixins)) + (target,)

    composed = new_class(
        composed_name,
        bases,
        {},
        lambda ns: ns.update(namespace),
    )

    composed.__horilla_composed__ = True
    composed.__horilla_filter_path__ = target_path
    composed.__wrapped_filter__ = target
    composed.__module__ = target.__module__
    composed.__qualname__ = f"{target.__qualname__}Extended"

    return composed
