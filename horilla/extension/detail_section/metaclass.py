"""
Registration for DetailSectionExtension subclasses (_inherit_detail_section).
"""

from __future__ import annotations

from django.apps import apps as django_apps
from django.core.exceptions import AppRegistryNotReady

from horilla.extension.detail_section.registry import (
    DetailSectionExtensionSpec,
    register_detail_section_extension,
)

_SKIP_KEYS = frozenset(
    {
        "_inherit_detail_section",
        "_inherit_detail_section_priority",
        "override_attrs",
        "__module__",
        "__qualname__",
        "__doc__",
    }
)

_LAYOUT_KEYS = frozenset(
    {
        "body_insert",
        "body_append",
        "excluded_fields_append",
        "include_fields_append",
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


def _validate_inherit_detail_section_path(inherit_detail_section: str) -> None:
    parts = inherit_detail_section.rsplit(".", 1)
    if len(parts) != 2:
        raise ValueError(
            "_inherit_detail_section must be '<module>.<ClassName>', got: "
            f"{inherit_detail_section!r}"
        )
    module_name, class_name = parts
    if not module_name or not class_name:
        raise ValueError(
            "_inherit_detail_section must be '<module>.<ClassName>', got: "
            f"{inherit_detail_section!r}"
        )


def register_detail_section_extension_class(cls: type) -> None:
    """Capture contributions from a DetailSectionExtension subclass."""
    inherit_detail_section = getattr(cls, "_inherit_detail_section", None)
    if not inherit_detail_section:
        return

    _validate_inherit_detail_section_path(inherit_detail_section)

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

    spec = DetailSectionExtensionSpec(
        inherit_detail_section=inherit_detail_section,
        class_name=cls.__name__,
        module=cls.__module__,
        extension_app_label=_resolve_extension_app_label(cls.__module__),
        priority=int(getattr(cls, "_inherit_detail_section_priority", 0) or 0),
        class_attrs=class_attrs,
        body_insert=list(getattr(cls, "body_insert", None) or []),
        body_append=list(getattr(cls, "body_append", None) or []),
        excluded_fields_append=list(getattr(cls, "excluded_fields_append", None) or []),
        include_fields_append=list(getattr(cls, "include_fields_append", None) or []),
        override_attrs=frozenset(getattr(cls, "override_attrs", ()) or ()),
    )
    register_detail_section_extension(spec)
    cls._is_detail_section_extension = True
    _compose_registered_target(inherit_detail_section)


def _compose_registered_target(target_path: str) -> None:
    """Compose one target when its target view class is already importable."""
    try:
        from horilla.extension.detail_section.bootstrap import (
            apply_detail_section_extensions,
        )

        apply_detail_section_extensions()
    except Exception:
        pass


class DetailSectionExtension:
    """
    Base class for detail-section (Details-tab) view extensions.
    Subclasses must set _inherit_detail_section.

    Do not instantiate — URL routing uses resolve_detail_section_view_class()
    on the target view.
    """

    _inherit_detail_section = None
    _inherit_detail_section_priority = 0
    override_attrs = ()
    _is_detail_section_extension = False

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if cls is DetailSectionExtension:
            return
        if getattr(cls, "_inherit_detail_section", None):
            register_detail_section_extension_class(cls)

    def __init__(self, *args, **kwargs):
        if self.__class__ is not DetailSectionExtension:
            raise TypeError(
                f"{self.__class__.__name__} is a detail-section extension registration "
                "class; use the composed target view via URL routing instead."
            )
        super().__init__(*args, **kwargs)
