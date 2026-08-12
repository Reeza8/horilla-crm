"""
Registration for FormExtension subclasses (_inherit_form).
"""

from __future__ import annotations

from django import forms
from django.apps import apps as django_apps
from django.core.exceptions import AppRegistryNotReady

from horilla.extension.forms.registry import (
    LAYOUT_KEYS,
    ExtensionSpec,
    register_extension,
)

_SKIP_KEYS = frozenset(
    {
        "_inherit_form",
        "_inherit_form_priority",
        "override_fields",
        "__module__",
        "__qualname__",
        "__doc__",
        "Meta",
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


def _validate_inherit_form_path(inherit_form: str) -> None:
    parts = inherit_form.rsplit(".", 1)
    if len(parts) != 2:
        raise ValueError(
            f"_inherit_form must be '<module>.<ClassName>', got: {inherit_form!r}"
        )
    module_name, class_name = parts
    if not module_name or not class_name:
        raise ValueError(
            f"_inherit_form must be '<module>.<ClassName>', got: {inherit_form!r}"
        )


def _extract_meta_attrs(meta) -> dict:
    if meta is None:
        return {}
    attrs = {}
    for key in (
        "exclude",
        "keep_on_form",
        "widgets",
        "labels",
        "help_texts",
        "error_messages",
        "fields_append",
    ):
        if hasattr(meta, key):
            attrs[key] = getattr(meta, key)
    return attrs


def register_extension_class(cls: type) -> None:
    """Capture contributions from a FormExtension subclass."""
    inherit_form = getattr(cls, "_inherit_form", None)
    if not inherit_form:
        return

    _validate_inherit_form_path(inherit_form)

    declared_fields = {
        key: value
        for key, value in cls.__dict__.items()
        if isinstance(value, forms.Field)
    }

    class_attrs = {
        key: value for key, value in cls.__dict__.items() if key in LAYOUT_KEYS
    }

    methods = {
        key: value
        for key, value in cls.__dict__.items()
        if callable(value)
        and key not in _SKIP_KEYS
        and key not in LAYOUT_KEYS
        and not isinstance(value, (classmethod, staticmethod))
        and not key.startswith("__")
    }
    class_attrs.update(methods)

    spec = ExtensionSpec(
        inherit_form=inherit_form,
        class_name=cls.__name__,
        module=cls.__module__,
        extension_app_label=_resolve_extension_app_label(cls.__module__),
        priority=int(getattr(cls, "_inherit_form_priority", 0) or 0),
        declared_fields=declared_fields,
        meta_attrs=_extract_meta_attrs(cls.__dict__.get("Meta")),
        class_attrs=class_attrs,
        field_order_insert=list(getattr(cls, "field_order_insert", None) or []),
        field_order_append=list(getattr(cls, "field_order_append", None) or []),
        step_fields_insert=dict(getattr(cls, "step_fields_insert", None) or {}),
        step_fields_append=dict(getattr(cls, "step_fields_append", None) or {}),
        fieldsets_insert=list(getattr(cls, "fieldsets_insert", None) or []),
        override_fields=frozenset(getattr(cls, "override_fields", ()) or ()),
    )
    register_extension(spec)
    cls._is_form_extension = True


class FormExtension:
    """
    Base class for form extensions. Subclasses must set _inherit_form.

    Do not instantiate — views use resolve_form_class() on the target form.
    """

    _inherit_form = None
    _inherit_form_priority = 0
    override_fields = ()
    _is_form_extension = False

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if cls is FormExtension:
            return
        if getattr(cls, "_inherit_form", None):
            register_extension_class(cls)

    def setup_form_extension_fields(self):
        """
        Override on subclasses to tweak widgets, required flags, querysets, etc.

        Called from the composed form ``__init__`` after the target form
        finishes building fields (safe to use ``self.fields``).
        """

    def __init__(self, *args, **kwargs):
        if self.__class__ is not FormExtension:
            raise TypeError(
                f"{self.__class__.__name__} is a form extension registration class; "
                "instantiate the composed target form via the view instead."
            )
        super().__init__(*args, **kwargs)
