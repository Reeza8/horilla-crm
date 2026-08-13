"""
Registration for DateTimeFormatterExtension subclasses (_inherit_formatter).
"""

from __future__ import annotations

from django.apps import apps as django_apps
from django.core.exceptions import AppRegistryNotReady

from horilla.extension.formatting.registry import (
    FormatterExtensionSpec,
    register_formatter_extension,
)

_SKIP_KEYS = frozenset(
    {
        "_inherit_formatter",
        "_inherit_formatter_priority",
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


def _validate_inherit_formatter_path(inherit_formatter: str) -> None:
    parts = inherit_formatter.rsplit(".", 1)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ValueError(
            "_inherit_formatter must be '<module>.<ClassName>', "
            f"got: {inherit_formatter!r}"
        )


def register_formatter_extension_class(cls: type) -> None:
    """Capture method overrides from a DateTimeFormatterExtension subclass."""
    inherit_formatter = getattr(cls, "_inherit_formatter", None)
    if not inherit_formatter:
        return

    _validate_inherit_formatter_path(inherit_formatter)

    methods = {
        key: value
        for key, value in cls.__dict__.items()
        if callable(value)
        and key not in _SKIP_KEYS
        and not isinstance(value, (classmethod, staticmethod))
        and not key.startswith("__")
    }

    spec = FormatterExtensionSpec(
        inherit_formatter=inherit_formatter,
        class_name=cls.__name__,
        module=cls.__module__,
        extension_app_label=_resolve_extension_app_label(cls.__module__),
        priority=int(getattr(cls, "_inherit_formatter_priority", 0) or 0),
        methods=methods,
    )
    register_formatter_extension(spec)
    cls._is_formatter_extension = True


class DateTimeFormatterExtension:
    """
    Base class for date/time formatter extensions.

    Subclasses must set ``_inherit_formatter`` to the target class path and may
    override ``format_datetime``, ``format_date``, ``format_time``, ``format``,
    ``parse_date``, or ``parse_datetime``.

    Do not instantiate — use ``resolve_datetime_formatter()`` / ``get_datetime_formatter()``.
    """

    _inherit_formatter = None
    _inherit_formatter_priority = 0
    _is_formatter_extension = False

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if cls is DateTimeFormatterExtension:
            return
        if getattr(cls, "_inherit_formatter", None):
            register_formatter_extension_class(cls)

    def __init__(self, *args, **kwargs):
        if self.__class__ is not DateTimeFormatterExtension:
            raise TypeError(
                f"{self.__class__.__name__} is a formatter extension registration "
                "class; use get_datetime_formatter() instead."
            )
        super().__init__(*args, **kwargs)
