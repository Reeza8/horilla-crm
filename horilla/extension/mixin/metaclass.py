"""
Registration for MixinExtension subclasses (_inherit_mixin).
"""

from __future__ import annotations

from django.apps import apps as django_apps
from django.core.exceptions import AppRegistryNotReady

from horilla.extension.mixin.registry import (
    MixinExtensionSpec,
    register_mixin_extension,
)

_SKIP_KEYS = frozenset(
    {
        "_inherit_mixin",
        "_inherit_mixin_priority",
        "__module__",
        "__qualname__",
        "__doc__",
        "__init_subclass__",
        "__new__",
        "__class__",
        "__dict__",
        "__weakref__",
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


def _validate_inherit_mixin_path(inherit_mixin: str) -> None:
    parts = inherit_mixin.rsplit(".", 1)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ValueError(
            "_inherit_mixin must be '<module>.<ClassName>' or "
            f"'<module>.<function_name>', got: {inherit_mixin!r}"
        )


def register_mixin_extension_class(cls: type) -> None:
    """Capture method/function overrides from a MixinExtension subclass."""
    inherit_mixin = getattr(cls, "_inherit_mixin", None)
    if not inherit_mixin:
        return

    _validate_inherit_mixin_path(inherit_mixin)

    methods = {
        key: value
        for key, value in cls.__dict__.items()
        if callable(value)
        and key not in _SKIP_KEYS
        and not isinstance(value, (classmethod, staticmethod))
    }

    spec = MixinExtensionSpec(
        inherit_mixin=inherit_mixin,
        class_name=cls.__name__,
        module=cls.__module__,
        extension_app_label=_resolve_extension_app_label(cls.__module__),
        priority=int(getattr(cls, "_inherit_mixin_priority", 0) or 0),
        methods=methods,
    )
    register_mixin_extension(spec)
    cls._is_mixin_extension = True

    from horilla.extension.mixin.bootstrap import apply_mixin_extensions

    apply_mixin_extensions()


class MixinExtension:
    """
    Base class for extending a bare mixin class or a module-level function
    that no other ``_inherit_*`` mechanism can reach — neither is ever
    dispatched via ``as_view()`` or resolved via a ``get_*_class()`` call, so
    there is no per-request resolution point to hook into the way
    ``_inherit_view``/``_inherit_form``/etc. do.

    Subclasses must set ``_inherit_mixin`` to the target path:

    - ``"<module>.<ClassName>"`` for a plain (non-Django-View) mixin class
      already composed into consumers via ordinary Python inheritance (e.g.
      ``HorillaListFilterFieldsMixin``, mixed into ``HorillaListView``).
      Extensions are applied **directly onto the target class once, at
      startup** — every existing and future subclass picks up the change
      automatically through normal attribute lookup, the same way the
      target's own methods reach subclasses.
    - ``"<module>.<function_name>"`` for a bare module-level function (e.g.
      ``get_export_cell_value``). Extensions are applied by reassigning the
      function's name in its defining module — callers that read the name
      fresh from the module (not a stale imported reference) automatically
      see the extended version.

    Because the target is patched directly rather than composed into a new
    subclass (CPython refuses ``__bases__`` reassignment for arbitrary
    plain classes — see ``compose.py``), a plain zero-arg ``super()`` call
    inside an override does **not** work here — the same documented
    restriction ``_inherit_model``'s ``clean()`` chaining already has
    ("Do not call ``super().clean()``; target ``clean()`` runs first").
    Instead, every overriding method/function takes an explicit ``original``
    as its **second** parameter (right after ``self``) — the previous layer
    (another extension, or the real target), already bound and ready to
    call with the target's own remaining arguments:

    .. code-block:: python

        class MyMixinExtension(MixinExtension):
            _inherit_mixin = "horilla.contrib.generics.mixins.HorillaListFilterFieldsMixin"

            def _get_model_fields(self, original, *args, **kwargs):
                fields = original(*args, **kwargs)
                fields.append({"name": "my_field", "type": "text"})
                return fields

    For a **function** target (e.g. ``get_export_cell_value``), the method
    is still written inside a class body like every other extension here,
    but ``self`` is always ``None`` when it runs — there is no instance,
    only a bare function, so ``self`` exists solely so the method can be
    declared the same way as a class-target override:

    .. code-block:: python

        class MyCellExtension(MixinExtension):
            _inherit_mixin = "horilla.contrib.core.views.export_data.get_export_cell_value"

            def get_export_cell_value(self, original, obj, field_name, field, user):
                if str(field_name).startswith("cf_"):
                    return str(obj.__dict__.get(field_name, ""))
                return original(obj, field_name, field, user)

    A class-target override method name may be a dunder (``__init__``,
    etc.) — only ``_inherit_mixin``/``_inherit_mixin_priority`` themselves,
    the standard non-method class attributes (``__module__``,
    ``__qualname__``, ``__doc__``), and a small set of dangerous/meaningless
    dunders (``__init_subclass__``, ``__new__``, ``__class__``, ``__dict__``,
    ``__weakref__``) are excluded from capture. ``__init__`` is the one
    dunder worth overriding in practice — e.g. a plain ``django.forms.Form``
    whose own ``__init__`` both builds and immediately filters a field's
    choices in one call, so there is no "after real ``__init__``" hook
    (``FormExtension.setup_form_extension_fields()``) that would run early
    enough:

    .. code-block:: python

        class MyColumnFormExtension(MixinExtension):
            _inherit_mixin = "horilla.contrib.generics.forms.generics.ColumnSelectionForm"

            def __init__(self, original, *args, **kwargs):
                original(*args, **kwargs)  # runs the real __init__ on self
                self.fields["visible_fields"].choices += [("my_field", "My Field")]

    Do not instantiate — this is a registration-only class.
    """

    _inherit_mixin = None
    _inherit_mixin_priority = 0
    _is_mixin_extension = False

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if cls is MixinExtension:
            return
        if getattr(cls, "_inherit_mixin", None):
            register_mixin_extension_class(cls)

    def __init__(self, *args, **kwargs):
        if self.__class__ is not MixinExtension:
            raise TypeError(
                f"{self.__class__.__name__} is a mixin extension registration "
                "class; it is applied directly to its target, not instantiated."
            )
        super().__init__(*args, **kwargs)
