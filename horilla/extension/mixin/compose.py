"""
Apply Mixin extensions (_inherit_mixin) directly onto their target.

Unlike every other ``_inherit_*`` package, there is no per-request
resolution step here (no ``as_view()`` wrapper, no ``get_*_class()`` call) —
the target itself is never dispatched or resolved by anything. Instead each
registered method/function is applied directly onto the target, once, the
same way ``_inherit_model`` injects methods onto a target model instead of
composing a new subclass.
"""

from __future__ import annotations

import functools


def _import_target(path: str):
    module_name, attr_name = path.rsplit(".", 1)
    module = __import__(module_name, fromlist=[attr_name])
    return module, attr_name, getattr(module, attr_name)


def _make_chained_method(original, extension_method):
    """
    Return a method that calls ``extension_method`` with the previous layer
    bound as its first extra argument, so the extension can decide whether
    (and how) to call through to it — mirrors ``custom_fields``'s own
    ``_build_row_q``/``handle_export``-style patches, just generalized.

    ``extension_method(self, original, *args, **kwargs)`` — ``original`` is
    already bound to ``self`` via ``functools.partial``, so an extension
    calls it as ``original(*args, **kwargs)``, not ``original(self, ...)``.
    """

    @functools.wraps(extension_method)
    def chained(self, *args, **kwargs):
        bound_original = functools.partial(original, self)
        return extension_method(self, bound_original, *args, **kwargs)

    return chained


def _make_chained_function(original, extension_function):
    """
    Same idea as ``_make_chained_method``, for a bare module-level function.

    ``extension_function`` is captured from a ``MixinExtension`` subclass's
    ``__dict__`` (see ``metaclass.py``), so it is a plain, never-bound
    function object with an ``self`` parameter in its signature — but the
    real call site (e.g. ``get_export_cell_value(obj, field_name, field,
    user)`` inside ``iter_export_rows``) never has a "self" to pass; there
    is no instance, only a bare function. Call it with a throwaway ``None``
    for that first parameter instead of a real instance — the parameter
    exists only so the method can be written inside a class body like every
    other extension in this app, not because it carries any instance state.
    """

    @functools.wraps(extension_function)
    def chained(*args, **kwargs):
        return extension_function(None, original, *args, **kwargs)

    return chained


def apply_mixin_class_extensions(target_class: type, specs) -> None:
    """
    Apply every registered method override directly onto ``target_class``,
    chaining specs in priority order (each wraps the previous layer, so the
    highest-priority spec's method runs outermost).
    """
    for spec in specs:
        for method_name, method in spec.methods.items():
            original = target_class.__dict__.get(method_name) or getattr(
                target_class, method_name, None
            )
            if original is None:
                setattr(target_class, method_name, method)
                continue
            setattr(
                target_class,
                method_name,
                _make_chained_method(original, method),
            )


def apply_mixin_function_extensions(module, attr_name: str, specs) -> None:
    """
    Apply every registered function override by reassigning ``attr_name`` on
    ``module``, chaining specs in priority order.
    """
    for spec in specs:
        # A function target has exactly one overridable name: the extension
        # method must be named the same as the target function so callers
        # (which import/call the bare name) see the composed version.
        replacement = spec.methods.get(attr_name)
        if replacement is None:
            continue
        original = getattr(module, attr_name)
        setattr(module, attr_name, _make_chained_function(original, replacement))


def apply_mixin_extension(target_path: str, specs) -> bool:
    """
    Apply all registered specs for ``target_path`` (a class or a function).

    Returns True if anything was applied.
    """
    if not specs:
        return False

    module, attr_name, target = _import_target(target_path)

    if isinstance(target, type):
        apply_mixin_class_extensions(target, specs)
    else:
        apply_mixin_function_extensions(module, attr_name, specs)
    return True
