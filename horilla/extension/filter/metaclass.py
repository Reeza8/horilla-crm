"""
Registration for FilterExtension subclasses (_inherit_filter).
"""

from __future__ import annotations

import django_filters
from django.apps import apps as django_apps
from django.core.exceptions import AppRegistryNotReady

from horilla.extension.filter.registry import (
    FilterExtensionSpec,
    register_filter_extension,
)

_SKIP_KEYS = frozenset(
    {
        "_inherit_filter",
        "_inherit_filter_priority",
        "override_filters",
        "__module__",
        "__qualname__",
        "__doc__",
        "Meta",
    }
)

_LAYOUT_KEYS = frozenset(
    {
        "search_fields_insert",
        "search_fields_append",
        "exclude_append",
        "fields_append",
    }
)


def _resolve_extension_app_label(module_name: str) -> str:
    if not module_name:
        return ""
    try:
        config = django_apps.get_containing_app_config(module_name)
        if config:
            return config.label
    except AppRegistryNotReady:
        pass
    return module_name.split(".")[0]


def _validate_inherit_filter_path(inherit_filter: str) -> None:
    parts = inherit_filter.rsplit(".", 1)
    if len(parts) != 2:
        raise ValueError(
            f"_inherit_filter must be '<module>.<ClassName>', got: {inherit_filter!r}"
        )
    module_name, class_name = parts
    if not module_name or not class_name:
        raise ValueError(
            f"_inherit_filter must be '<module>.<ClassName>', got: {inherit_filter!r}"
        )


def _extract_meta_attrs(meta) -> dict:
    if meta is None:
        return {}
    attrs = {}
    for key in (
        "exclude",
        "search_fields",
        "fields",
        "fields_append",
        "name_split_fields",
    ):
        if hasattr(meta, key):
            attrs[key] = getattr(meta, key)
    return attrs


def _is_declared_filter(value) -> bool:
    return isinstance(value, django_filters.Filter)


def register_filter_extension_class(cls: type) -> None:
    """Capture contributions from a FilterExtension subclass."""
    inherit_filter = getattr(cls, "_inherit_filter", None)
    if not inherit_filter:
        return

    _validate_inherit_filter_path(inherit_filter)

    declared_filters = {
        key: value for key, value in cls.__dict__.items() if _is_declared_filter(value)
    }

    class_attrs = {
        key: value for key, value in cls.__dict__.items() if key in _LAYOUT_KEYS
    }

    methods = {
        key: value
        for key, value in cls.__dict__.items()
        if callable(value)
        and key not in _SKIP_KEYS
        and key not in _LAYOUT_KEYS
        and not isinstance(value, (classmethod, staticmethod))
        and not key.startswith("__")
    }
    class_attrs.update(methods)

    spec = FilterExtensionSpec(
        inherit_filter=inherit_filter,
        class_name=cls.__name__,
        module=cls.__module__,
        extension_app_label=_resolve_extension_app_label(cls.__module__),
        priority=int(getattr(cls, "_inherit_filter_priority", 0) or 0),
        declared_filters=declared_filters,
        meta_attrs=_extract_meta_attrs(cls.__dict__.get("Meta")),
        class_attrs=class_attrs,
        search_fields_insert=list(getattr(cls, "search_fields_insert", None) or []),
        search_fields_append=list(getattr(cls, "search_fields_append", None) or []),
        exclude_append=list(getattr(cls, "exclude_append", None) or []),
        fields_append=list(getattr(cls, "fields_append", None) or []),
        override_filters=frozenset(getattr(cls, "override_filters", ()) or ()),
    )
    register_filter_extension(spec)
    cls._is_filter_extension = True
    _compose_registered_target(inherit_filter)


def _compose_registered_target(target_path: str) -> None:
    try:
        from horilla.extension.filter.bootstrap import apply_filter_extensions

        apply_filter_extensions()
    except Exception:
        pass


class FilterExtension:
    """
    Base class for filterset extensions. Subclasses must set _inherit_filter.

    Do not instantiate — views use resolve_filterset_class() on the target filterset.
    """

    _inherit_filter = None
    _inherit_filter_priority = 0
    override_filters = ()
    _is_filter_extension = False

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if cls is FilterExtension:
            return
        if getattr(cls, "_inherit_filter", None):
            register_filter_extension_class(cls)

    def setup_filter_extension(self):
        """
        Optional hook after FilterSet __init__.

        Override to tweak filter instances (querysets, labels, etc.).
        """

    def __init__(self, *args, **kwargs):
        if self.__class__ is not FilterExtension:
            raise TypeError(
                f"{self.__class__.__name__} is a filter extension registration class; "
                "use the composed target filterset via the view instead."
            )
        super().__init__(*args, **kwargs)
