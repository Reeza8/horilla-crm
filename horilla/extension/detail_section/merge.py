"""
Merge detail-section view class attributes from extension specs onto a
target HorillaDetailSectionView.
"""

from __future__ import annotations

from types import SimpleNamespace

from horilla.extension.detail_section.registry import DetailSectionExtensionSpec
from horilla.extension.list.merge import merge_append_attr, merge_columns

__all__ = ["merge_body", "merge_append_attr"]


def _body_column_specs(
    specs: list[DetailSectionExtensionSpec],
) -> list[SimpleNamespace]:
    return [
        SimpleNamespace(
            columns_insert=spec.body_insert,
            columns_append=spec.body_append,
        )
        for spec in specs
    ]


def merge_body(
    base_body: list | None, specs: list[DetailSectionExtensionSpec]
) -> list | None:
    """Apply body_insert / body_append from all specs."""
    return merge_columns(base_body, _body_column_specs(specs))
