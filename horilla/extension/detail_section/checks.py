"""
Django system checks for _inherit_detail_section extensions.
"""

from django.core.checks import Error, Tags, register

from horilla.contrib.generics.views.detail_tabs import HorillaDetailSectionView
from horilla.extension.detail_section.registry import DETAIL_SECTION_EXTENSION_REGISTRY


@register(Tags.models, id="detail_section_extensions")
def check_detail_section_extensions(app_configs, **kwargs):
    """Validate registered detail-section extension targets at startup."""
    errors = []
    for target_path, specs in DETAIL_SECTION_EXTENSION_REGISTRY.items():
        parts = target_path.rsplit(".", 1)
        if len(parts) != 2:
            errors.append(
                Error(
                    f"Invalid _inherit_detail_section path: {target_path!r}",
                    id="detail_section_extensions.E001",
                )
            )
            continue
        module_name, class_name = parts
        try:
            module = __import__(module_name, fromlist=[class_name])
            view_cls = getattr(module, class_name)
        except Exception as exc:
            errors.append(
                Error(
                    f"Cannot import detail-section view target {target_path!r}: {exc}",
                    id="detail_section_extensions.E002",
                )
            )
            continue
        if not isinstance(view_cls, type) or not issubclass(
            view_cls, HorillaDetailSectionView
        ):
            errors.append(
                Error(
                    f"{target_path!r} must be a HorillaDetailSectionView subclass",
                    id="detail_section_extensions.E003",
                )
            )
            continue
        if view_cls is HorillaDetailSectionView:
            errors.append(
                Error(
                    f"{target_path!r} must be a concrete HorillaDetailSectionView "
                    "subclass",
                    id="detail_section_extensions.E004",
                )
            )
        _ = specs
    return errors
