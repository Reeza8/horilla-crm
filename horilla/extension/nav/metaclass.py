"""
Registration for NavExtension subclasses (_inherit_nav).
"""

from __future__ import annotations

from django.apps import apps as django_apps
from django.core.exceptions import AppRegistryNotReady

from horilla.extension.nav.registry import NavExtensionSpec, register_nav_extension

_SKIP_KEYS = frozenset(
    {
        "_inherit_nav",
        "_inherit_nav_priority",
        "override_attrs",
        "__module__",
        "__qualname__",
        "__doc__",
    }
)

_LAYOUT_KEYS = frozenset(
    {
        "actions_append",
        "custom_view_type_update",
        "column_selector_exclude_fields_append",
        "exclude_kanban_fields_append",
        "navbar_indication_attrs_update",
    }
)

_SCALAR_OVERRIDE_KEYS = frozenset(
    {
        "filterset_class",
        "default_layout",
        "enable_quick_filters",
        "enable_actions",
        "filter_option",
        "search_option",
        "recently_viewed_option",
        "all_view_types",
        "one_view_only",
        "reload_option",
        "border_enabled",
        "search_push_url",
        "navbar_indication",
        "save_to_list_option",
        "nav_width",
        "template_name",
        "main_session_id",
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


def _validate_inherit_nav_path(inherit_nav: str) -> None:
    parts = inherit_nav.rsplit(".", 1)
    if len(parts) != 2:
        raise ValueError(
            f"_inherit_nav must be '<module>.<ClassName>', got: {inherit_nav!r}"
        )
    module_name, class_name = parts
    if not module_name or not class_name:
        raise ValueError(
            f"_inherit_nav must be '<module>.<ClassName>', got: {inherit_nav!r}"
        )


def register_nav_extension_class(cls: type) -> None:
    """Capture contributions from a NavExtension subclass."""
    inherit_nav = getattr(cls, "_inherit_nav", None)
    if not inherit_nav:
        return

    _validate_inherit_nav_path(inherit_nav)

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

    spec = NavExtensionSpec(
        inherit_nav=inherit_nav,
        class_name=cls.__name__,
        module=cls.__module__,
        extension_app_label=_resolve_extension_app_label(cls.__module__),
        priority=int(getattr(cls, "_inherit_nav_priority", 0) or 0),
        class_attrs=class_attrs,
        actions_append=list(getattr(cls, "actions_append", None) or []),
        custom_view_type_update=dict(
            getattr(cls, "custom_view_type_update", None) or {}
        ),
        column_selector_exclude_fields_append=list(
            getattr(cls, "column_selector_exclude_fields_append", None) or []
        ),
        exclude_kanban_fields_append=list(
            getattr(cls, "exclude_kanban_fields_append", None) or []
        ),
        navbar_indication_attrs_update=dict(
            getattr(cls, "navbar_indication_attrs_update", None) or {}
        ),
        scalar_overrides=scalar_overrides,
        override_attrs=frozenset(getattr(cls, "override_attrs", ()) or ()),
    )
    register_nav_extension(spec)
    cls._is_nav_extension = True
    _compose_registered_target(inherit_nav)


def _compose_registered_target(target_path: str) -> None:
    try:
        from horilla.extension.nav.bootstrap import apply_nav_extensions

        apply_nav_extensions()
    except Exception:
        pass


class NavExtension:
    """
    Base class for nav view extensions. Subclasses must set _inherit_nav.

    Do not instantiate — URL routing uses resolve_nav_view_class() on the target view.
    """

    _inherit_nav = None
    _inherit_nav_priority = 0
    override_attrs = ()
    _is_nav_extension = False

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if cls is NavExtension:
            return
        if getattr(cls, "_inherit_nav", None):
            register_nav_extension_class(cls)

    def setup_nav_view_extension(self):
        """
        Optional hook after the view instance is created.

        Override to tweak per-request navbar state (rare). Prefer class-level
        layout hooks (actions_append) or method overrides with super().
        """

    def __init__(self, *args, **kwargs):
        if self.__class__ is not NavExtension:
            raise TypeError(
                f"{self.__class__.__name__} is a nav extension registration class; "
                "use the composed target view via URL routing instead."
            )
        super().__init__(*args, **kwargs)
