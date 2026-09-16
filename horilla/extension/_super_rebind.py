"""
Fix zero-arg ``super()`` for extension methods copied into generated mixins.

Every ``_spec_to_mixin()`` across horilla.extension (forms, detail,
detail_section, list, kanban, card, nav, tab, filter, view, formatting)
builds a brand-new mixin class and copies an extension author's methods into
it by reference: ``type(mixin_name, (), {"clean": ExtSubclass.__dict__["clean"], ...})``.

A method written with zero-arg ``super()`` (``def clean(self): return
super().clean()``) relies on an implicit ``__class__`` closure cell that the
compiler binds to the class the method was textually defined in — here,
the extension author's own ``FormExtension``/``DetailExtension`` subclass.
That subclass is never actually part of the composed MRO (only the
freshly built mixin is), so the original cell points at the wrong class:
``super(ExtSubclass, self)`` raises ``TypeError`` because ``self`` (a
composed-form instance) is not an instance of ``ExtSubclass``.

Without this fix, the only way to call "the rest of the chain" from an
extension method is to call the concrete target class's method directly
(``TargetClass.clean(self)``) — which works when exactly one extension
overrides that method name, but silently skips every *other* extension
overriding the same name once two or more are registered for the same
target, since normal attribute lookup only reaches the first mixin in the
MRO.

``rebind_method_super()`` gives each copied method its own working
``__class__`` cell bound to the mixin it actually lives in, so ordinary
``super().clean()`` (or ``super().get_context_data(**kwargs)``, etc.)
correctly chains to the next extension — or, once there is only one link
left, to the real target class — regardless of how many extensions are
stacked.
"""

from __future__ import annotations

import types
from typing import Any


def rebind_method_super(func: Any, mixin: type) -> Any:
    """
    Return ``func`` rebound so its zero-arg ``super()`` resolves against
    ``mixin`` instead of the class it was originally defined in.

    Returns ``func`` unchanged when it is not a plain function, or does not
    reference ``__class__`` (i.e. does not use zero-arg ``super()`` /
    ``__class__`` at all) — classmethods, staticmethods, properties, and
    ordinary values (declared fields, layout lists) pass through untouched.
    """
    if not isinstance(func, types.FunctionType):
        return func
    freevars = func.__code__.co_freevars
    if "__class__" not in freevars or not func.__closure__:
        return func

    index = freevars.index("__class__")
    new_closure = list(func.__closure__)
    new_closure[index] = types.CellType(mixin)

    return types.FunctionType(
        func.__code__,
        func.__globals__,
        name=func.__name__,
        argdefs=func.__defaults__,
        closure=tuple(new_closure),
    )


def rebind_namespace_supers(namespace: dict[str, Any], mixin: type) -> None:
    """
    Rebind every zero-arg-``super()``-using function in ``namespace`` (in
    place) to resolve against ``mixin``.

    Call this exactly once, right after building ``mixin`` via
    ``type(mixin_name, (), namespace)`` — the functions already live in
    ``namespace`` (which became ``mixin.__dict__``), so this reassigns each
    one on the class via ``setattr``.
    """
    for key, value in list(namespace.items()):
        rebound = rebind_method_super(value, mixin)
        if rebound is not value:
            setattr(mixin, key, rebound)
