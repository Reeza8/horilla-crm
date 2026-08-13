"""
Registration for ViewExtension subclasses (_inherit_view).
"""

from __future__ import annotations

from django.apps import apps as django_apps
from django.core.exceptions import AppRegistryNotReady

from horilla.extension.view.registry import ViewExtensionSpec, register_view_extension

_SKIP_KEYS = frozenset(
    {
        "_inherit_view",
        "_inherit_view_priority",
        "__module__",
        "__qualname__",
        "__doc__",
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


def _validate_inherit_view_path(inherit_view: str) -> None:
    parts = inherit_view.rsplit(".", 1)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ValueError(
            "_inherit_view must be '<module>.<ClassName>', " f"got: {inherit_view!r}"
        )


def register_view_extension_class(cls: type) -> None:
    """Capture method overrides from a ViewExtension subclass."""
    inherit_view = getattr(cls, "_inherit_view", None)
    if not inherit_view:
        return

    _validate_inherit_view_path(inherit_view)

    methods = {
        key: value
        for key, value in cls.__dict__.items()
        if callable(value)
        and key not in _SKIP_KEYS
        and not isinstance(value, (classmethod, staticmethod))
        and not key.startswith("__")
    }

    spec = ViewExtensionSpec(
        inherit_view=inherit_view,
        class_name=cls.__name__,
        module=cls.__module__,
        extension_app_label=_resolve_extension_app_label(cls.__module__),
        priority=int(getattr(cls, "_inherit_view_priority", 0) or 0),
        methods=methods,
    )
    register_view_extension(spec)
    cls._is_view_extension = True


class ViewExtension:
    """
    Base class for Horilla view extensions.

    Subclasses must set ``_inherit_view`` to the concrete target view path
    (e.g. ``EditFieldView``). Resolution runs through
    ``horilla.views.generic.View.as_view`` / ``resolve_view_class``.

    Do not instantiate extension registration classes.
    """

    _inherit_view = None
    _inherit_view_priority = 0
    _is_view_extension = False

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if cls is ViewExtension:
            return
        if getattr(cls, "_inherit_view", None):
            register_view_extension_class(cls)

    def __init__(self, *args, **kwargs):
        if self.__class__ is not ViewExtension:
            raise TypeError(
                f"{self.__class__.__name__} is a view extension registration "
                "class; use resolve_view_class(TargetView) instead."
            )
        super().__init__(*args, **kwargs)
