"""
Django system checks for _inherit_mixin extensions.
"""

from django.core.checks import Error, Tags, register

from horilla.extension.mixin.registry import MIXIN_EXTENSION_REGISTRY


@register(Tags.models, deploy=True)
def check_mixin_extensions(app_configs, **kwargs):
    """Validate registered mixin extension targets at startup."""
    errors = []
    for target_path, specs in MIXIN_EXTENSION_REGISTRY.items():
        parts = target_path.rsplit(".", 1)
        if len(parts) != 2 or not parts[0] or not parts[1]:
            errors.append(
                Error(
                    f"Invalid _inherit_mixin path: {target_path!r}",
                    id="mixin_extensions.E001",
                )
            )
            continue
        module_name, attr_name = parts
        try:
            module = __import__(module_name, fromlist=[attr_name])
            target = getattr(module, attr_name)
        except Exception as exc:
            errors.append(
                Error(
                    f"Cannot import mixin extension target {target_path!r}: {exc}",
                    id="mixin_extensions.E002",
                )
            )
            continue
        if isinstance(target, type):
            for spec in specs:
                for method_name in spec.methods:
                    if not hasattr(target, method_name) and not callable(
                        getattr(target, method_name, None)
                    ):
                        pass  # method_name may be new; that is allowed
        else:
            if not callable(target):
                errors.append(
                    Error(
                        f"{target_path!r} is neither a class nor a callable function",
                        id="mixin_extensions.E003",
                    )
                )
                continue
            for spec in specs:
                if attr_name not in spec.methods:
                    errors.append(
                        Error(
                            f"Extension {spec.module}.{spec.class_name} targets "
                            f"function {target_path!r} but does not define a "
                            f"method named {attr_name!r} to replace it",
                            id="mixin_extensions.E004",
                        )
                    )
    return errors
