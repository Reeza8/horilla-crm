"""
Debugging helpers for _inherit_mixin extensions.
"""

from __future__ import annotations

from horilla.extension.mixin.registry import MIXIN_APPLIED_MAP, get_mixin_extensions_for


def get_mixin_extensions(target_path: str) -> list:
    """Return extension specs registered for a target path."""
    return get_mixin_extensions_for(target_path)


def is_mixin_extension_applied(target_path: str) -> bool:
    """Return whether every registered spec for ``target_path`` has been applied."""
    specs = get_mixin_extensions_for(target_path)
    if not specs:
        return False
    applied = MIXIN_APPLIED_MAP.get(target_path, set())
    return all(id(spec) in applied for spec in specs)


def print_mixin_extension_chain(target_path: str) -> None:
    """Print the registered extensions for a target, in application order (stdout)."""
    specs = get_mixin_extensions_for(target_path)
    if not specs:
        print(f"No _inherit_mixin extensions registered for {target_path!r}")
        return
    print(f"{target_path!r} extensions (outermost last):")
    for spec in specs:
        print(f"  - {spec.module}.{spec.class_name} (priority={spec.priority})")
