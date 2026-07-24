"""
Registration for DetailExtension subclasses (_inherit_detail).
"""

from __future__ import annotations

from django.apps import apps as django_apps
from django.core.exceptions import AppRegistryNotReady

from horilla.extension.detail.registry import (
    DetailExtensionSpec,
    register_detail_extension,
)

_SKIP_KEYS = frozenset(
    {
        "_inherit_detail",
        "_inherit_detail_priority",
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
        "header_fields_insert",
        "header_fields_append",
        "excluded_fields_append",
        "split_excluded_fields_append",
        "actions_append",
        "badge_append",
        "breadcrumbs_append",
    }
)

_SCALAR_OVERRIDE_KEYS = frozenset(
    {
        "pipeline_field",
        "tab_url",
        "template_name",
        "context_object_name",
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


def _validate_inherit_detail_path(inherit_detail: str) -> None:
    parts = inherit_detail.rsplit(".", 1)
    if len(parts) != 2:
        raise ValueError(
            f"_inherit_detail must be '<module>.<ClassName>', got: {inherit_detail!r}"
        )
    module_name, class_name = parts
    if not module_name or not class_name:
        raise ValueError(
            f"_inherit_detail must be '<module>.<ClassName>', got: {inherit_detail!r}"
        )


def register_detail_extension_class(cls: type) -> None:
    """Capture contributions from a DetailExtension subclass."""
    inherit_detail = getattr(cls, "_inherit_detail", None)
    if not inherit_detail:
        return

    _validate_inherit_detail_path(inherit_detail)

    class_attrs = {
        key: value for key, value in cls.__dict__.items() if key in _LAYOUT_KEYS
    }

    methods = {
        key: value
        for key, value in cls.__dict__.items()
        if callable(value)
        and key not in _SKIP_KEYS
        and key not in _LAYOUT_KEYS
        and key not in _SCALAR_OVERRIDE_KEYS
        and not isinstance(value, (classmethod, staticmethod))
        and not key.startswith("__")
    }
    class_attrs.update(methods)

    scalar_overrides = {
        key: getattr(cls, key)
        for key in _SCALAR_OVERRIDE_KEYS
        if key in cls.__dict__ and not key.startswith("__")
    }

    spec = DetailExtensionSpec(
        inherit_detail=inherit_detail,
        class_name=cls.__name__,
        module=cls.__module__,
        extension_app_label=_resolve_extension_app_label(cls.__module__),
        priority=int(getattr(cls, "_inherit_detail_priority", 0) or 0),
        class_attrs=class_attrs,
        body_insert=list(getattr(cls, "body_insert", None) or []),
        body_append=list(getattr(cls, "body_append", None) or []),
        header_fields_insert=list(getattr(cls, "header_fields_insert", None) or []),
        header_fields_append=list(getattr(cls, "header_fields_append", None) or []),
        excluded_fields_append=list(getattr(cls, "excluded_fields_append", None) or []),
        split_excluded_fields_append=list(
            getattr(cls, "split_excluded_fields_append", None) or []
        ),
        actions_append=list(getattr(cls, "actions_append", None) or []),
        badge_append=list(getattr(cls, "badge_append", None) or []),
        breadcrumbs_append=list(getattr(cls, "breadcrumbs_append", None) or []),
        scalar_overrides=scalar_overrides,
        override_attrs=frozenset(getattr(cls, "override_attrs", ()) or ()),
    )
    register_detail_extension(spec)
    cls._is_detail_extension = True
    _compose_registered_target(inherit_detail)


def _compose_registered_target(target_path: str) -> None:
    """Compose one target when its target view class is already importable."""
    try:
        from horilla.extension.detail.bootstrap import apply_detail_extensions

        apply_detail_extensions()
    except Exception:
        pass


class DetailExtension:
    """
    Base class for detail view extensions. Subclasses must set _inherit_detail.

    Do not instantiate — URL routing uses resolve_detail_view_class() on the target view.
    """

    _inherit_detail = None
    _inherit_detail_priority = 0
    override_attrs = ()
    _is_detail_extension = False

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if cls is DetailExtension:
            return
        if getattr(cls, "_inherit_detail", None):
            register_detail_extension_class(cls)

    def setup_detail_view_extension(self):
        """
        Optional hook after the view instance is created.

        Override to tweak per-request detail state (rare). Prefer class-level
        layout hooks (body_insert) or method overrides with super().
        """

    def __init__(self, *args, **kwargs):
        if self.__class__ is not DetailExtension:
            raise TypeError(
                f"{self.__class__.__name__} is a detail extension registration class; "
                "use the composed target view via URL routing instead."
            )
        super().__init__(*args, **kwargs)
