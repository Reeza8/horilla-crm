"""
Merge detail view class attributes from extension specs onto a target HorillaDetailView.
"""

from __future__ import annotations

import copy
from types import SimpleNamespace

from horilla.extension.detail.registry import DetailExtensionSpec
from horilla.extension.list.merge import (
    merge_append_attr,
    merge_columns,
    merge_scalar_overrides,
)

__all__ = [
    "merge_body",
    "merge_fieldsets",
    "merge_header_fields",
    "merge_append_attr",
    "merge_scalar_overrides",
]


def _body_column_specs(specs: list[DetailExtensionSpec]) -> list[SimpleNamespace]:
    return [
        SimpleNamespace(
            columns_insert=spec.body_insert,
            columns_append=spec.body_append,
        )
        for spec in specs
    ]


def _header_column_specs(specs: list[DetailExtensionSpec]) -> list[SimpleNamespace]:
    return [
        SimpleNamespace(
            columns_insert=spec.header_fields_insert,
            columns_append=spec.header_fields_append,
        )
        for spec in specs
    ]


def merge_body(base_body: list | None, specs: list[DetailExtensionSpec]) -> list | None:
    """Apply body_insert / body_append from all specs."""
    return merge_columns(base_body, _body_column_specs(specs))


def merge_header_fields(
    base_header: list | None, specs: list[DetailExtensionSpec]
) -> list | None:
    """Apply header_fields_insert / header_fields_append from all specs."""
    return merge_columns(base_header, _header_column_specs(specs))


def merge_fieldsets(
    base_fieldsets: tuple | list | None, specs: list[DetailExtensionSpec]
) -> tuple | None:
    """
    Merge fieldsets_insert pairs into the target detail view's fieldsets layout.

    Same semantics as form ``fieldsets_insert``: insert ``new_field`` after
    ``after`` within the first fieldset that contains the anchor; otherwise
    append to the last fieldset.
    """
    if base_fieldsets is None and not any(s.fieldsets_insert for s in specs):
        return None

    merged = copy.deepcopy(list(base_fieldsets or ()))
    for spec in specs:
        for after, new_field in spec.fieldsets_insert or []:
            inserted = False
            for index, (name, options) in enumerate(merged):
                fields = list(options.get("fields", ()))
                if new_field in fields:
                    inserted = True
                    break
                if after in fields:
                    fields.insert(fields.index(after) + 1, new_field)
                    merged[index] = (name, {**options, "fields": tuple(fields)})
                    inserted = True
                    break
            if not inserted and merged:
                name, options = merged[-1]
                fields = list(options.get("fields", ()))
                if new_field not in fields:
                    fields.append(new_field)
                    merged[-1] = (name, {**options, "fields": tuple(fields)})
    return tuple(merged)
