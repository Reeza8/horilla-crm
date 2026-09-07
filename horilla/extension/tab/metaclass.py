"""
Registration for TabExtension subclasses (_inherit_tab).
"""

from __future__ import annotations

from django.apps import apps as django_apps
from django.core.exceptions import AppRegistryNotReady

from horilla.extension.tab.registry import TabExtensionSpec, register_tab_extension

_SKIP_KEYS = frozenset(
    {
        "_inherit_tab",
        "_inherit_tab_priority",
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


def _validate_inherit_tab_path(inherit_tab: str) -> None:
    parts = inherit_tab.rsplit(".", 1)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ValueError(
            "_inherit_tab must be '<module>.<ClassName>', " f"got: {inherit_tab!r}"
        )


def register_tab_extension_class(cls: type) -> None:
    """Capture method overrides from a TabExtension subclass."""
    inherit_tab = getattr(cls, "_inherit_tab", None)
    if not inherit_tab:
        return

    _validate_inherit_tab_path(inherit_tab)

    methods = {
        key: value
        for key, value in cls.__dict__.items()
        if callable(value)
        and key not in _SKIP_KEYS
        and not isinstance(value, (classmethod, staticmethod))
        and not key.startswith("__")
    }

    spec = TabExtensionSpec(
        inherit_tab=inherit_tab,
        class_name=cls.__name__,
        module=cls.__module__,
        extension_app_label=_resolve_extension_app_label(cls.__module__),
        priority=int(getattr(cls, "_inherit_tab_priority", 0) or 0),
        methods=methods,
    )
    register_tab_extension(spec)
    cls._is_tab_extension = True


class TabExtension:
    """
    Base class for Horilla tab view extensions.

    Subclasses must set ``_inherit_tab`` to the concrete target path
    (e.g. ``CompanyInformationTabView``). Resolution runs through
    ``HorillaTabView.as_view`` / ``resolve_tab_view_class``.

    Override ``get_tabs`` (preferred) and call the target explicitly::

        tabs = list(CompanyInformationTabView.get_tabs(self))
        tabs.append({...})
        return tabs

    Do not instantiate extension registration classes.
    """

    _inherit_tab = None
    _inherit_tab_priority = 0
    _is_tab_extension = False

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if cls is TabExtension:
            return
        if getattr(cls, "_inherit_tab", None):
            register_tab_extension_class(cls)

    def __init__(self, *args, **kwargs):
        if self.__class__ is not TabExtension:
            raise TypeError(
                f"{self.__class__.__name__} is a tab extension registration "
                "class; use resolve_tab_view_class(TargetTabView) instead."
            )
        super().__init__(*args, **kwargs)
