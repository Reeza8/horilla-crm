"""
Registration for KanbanExtension subclasses (_inherit_kanban).
"""

from __future__ import annotations

from django.apps import apps as django_apps
from django.core.exceptions import AppRegistryNotReady

from horilla.extension.kanban.registry import (
    KanbanExtensionSpec,
    register_kanban_extension,
)

_SKIP_KEYS = frozenset(
    {
        "_inherit_kanban",
        "_inherit_kanban_priority",
        "override_attrs",
        "__module__",
        "__qualname__",
        "__doc__",
    }
)

_LAYOUT_KEYS = frozenset(
    {
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
)

_SCALAR_OVERRIDE_KEYS = frozenset(
    {
        "filterset_class",
        "default_sort_field",
        "default_sort_direction",
        "paginate_by",
        "view_id",
        "filter_url_push",
        "enable_quick_filters",
        "bulk_update_option",
        "bulk_export_option",
        "list_column_visibility",
        "owner_filtration",
        "enable_sorting",
        "group_by_field",
        "kanban_order_by",
        "height_kanban",
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


def _validate_inherit_kanban_path(inherit_kanban: str) -> None:
    parts = inherit_kanban.rsplit(".", 1)
    if len(parts) != 2:
        raise ValueError(
            f"_inherit_kanban must be '<module>.<ClassName>', got: {inherit_kanban!r}"
        )
    module_name, class_name = parts
    if not module_name or not class_name:
        raise ValueError(
            f"_inherit_kanban must be '<module>.<ClassName>', got: {inherit_kanban!r}"
        )


def register_kanban_extension_class(cls: type) -> None:
    """Capture contributions from a KanbanExtension subclass."""
    inherit_kanban = getattr(cls, "_inherit_kanban", None)
    if not inherit_kanban:
        return

    _validate_inherit_kanban_path(inherit_kanban)

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

    spec = KanbanExtensionSpec(
        inherit_kanban=inherit_kanban,
        class_name=cls.__name__,
        module=cls.__module__,
        extension_app_label=_resolve_extension_app_label(cls.__module__),
        priority=int(getattr(cls, "_inherit_kanban_priority", 0) or 0),
        class_attrs=class_attrs,
        columns_insert=list(getattr(cls, "columns_insert", None) or []),
        columns_append=list(getattr(cls, "columns_append", None) or []),
        bulk_update_fields_append=list(
            getattr(cls, "bulk_update_fields_append", None) or []
        ),
        export_exclude_append=list(getattr(cls, "export_exclude_append", None) or []),
        exclude_columns_append=list(getattr(cls, "exclude_columns_append", None) or []),
        actions_append=list(getattr(cls, "actions_append", None) or []),
        custom_bulk_actions_append=list(
            getattr(cls, "custom_bulk_actions_append", None) or []
        ),
        additional_action_button_append=list(
            getattr(cls, "additional_action_button_append", None) or []
        ),
        exclude_quick_filter_fields_append=list(
            getattr(cls, "exclude_quick_filter_fields_append", None) or []
        ),
        exclude_columns_from_sorting_append=list(
            getattr(cls, "exclude_columns_from_sorting_append", None) or []
        ),
        exclude_kanban_fields_append=list(
            getattr(cls, "exclude_kanban_fields_append", None) or []
        ),
        scalar_overrides=scalar_overrides,
        override_attrs=frozenset(getattr(cls, "override_attrs", ()) or ()),
    )
    register_kanban_extension(spec)
    cls._is_kanban_extension = True
    _compose_registered_target(inherit_kanban)


def _compose_registered_target(target_path: str) -> None:
    """Compose one target when its target view class is already importable."""
    try:
        from horilla.extension.kanban.bootstrap import apply_kanban_extensions

        apply_kanban_extensions()
    except Exception:
        pass


class KanbanExtension:
    """
    Base class for kanban view extensions. Subclasses must set _inherit_kanban.

    Do not instantiate — URL routing uses resolve_kanban_view_class() on the target view.
    """

    _inherit_kanban = None
    _inherit_kanban_priority = 0
    override_attrs = ()
    _is_kanban_extension = False

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if cls is KanbanExtension:
            return
        if getattr(cls, "_inherit_kanban", None):
            register_kanban_extension_class(cls)

    def setup_kanban_view_extension(self):
        """
        Optional hook after the view instance is created.

        Override to tweak per-request kanban state (rare). Prefer class-level
        layout hooks (columns_insert) or method overrides with super().
        """

    def __init__(self, *args, **kwargs):
        if self.__class__ is not KanbanExtension:
            raise TypeError(
                f"{self.__class__.__name__} is a kanban extension registration class; "
                "use the composed target view via URL routing instead."
            )
        super().__init__(*args, **kwargs)
