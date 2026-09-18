"""
Merge list view class attributes from extension specs onto a target HorillaListView.
"""

from __future__ import annotations

from horilla.extension.list.registry import ListExtensionSpec


def column_key(column: str | tuple) -> str:
    """Normalize a column entry to its field name key."""
    if isinstance(column, (list, tuple)) and len(column) >= 2:
        return str(column[1])
    return str(column)


def _column_in_list(name: str, columns: list) -> bool:
    return any(column_key(col) == name for col in columns)


def _find_column_index(anchor: str, columns: list) -> int:
    for index, col in enumerate(columns):
        if column_key(col) == anchor:
            return index
    return -1


def merge_columns(
    base_columns: list | None, specs: list[ListExtensionSpec]
) -> list | None:
    """
    Apply columns_insert / columns_append from all specs.

    Returns ``None`` (meaning: leave the target's own ``columns`` alone)
    unless a spec actually inserts or appends a column — a registered spec
    with nothing to contribute here (e.g. a base-class extension that only
    overrides a method, not columns) must not overwrite the target's own
    ``columns``, and ``base_columns`` being ``None`` (a ``cached_property``/
    ``property`` the target computes per-instance — see
    ``horilla.extension.list.compose._static_class_attr``) must not be
    replaced by an empty list when there is nothing to merge in.
    """
    if not specs and not base_columns:
        return None

    merged = list(base_columns or [])
    changed = False

    for spec in specs:
        for after, new_col in spec.columns_insert:
            name = column_key(new_col)
            if _column_in_list(name, merged):
                continue
            index = _find_column_index(after, merged)
            if index >= 0:
                merged.insert(index + 1, new_col)
            else:
                merged.append(new_col)
            changed = True
        for new_col in spec.columns_append:
            name = column_key(new_col)
            if not _column_in_list(name, merged):
                merged.append(new_col)
                changed = True

    return merged if changed else None


def _union_sequence(*sequences) -> list:
    seen: set = set()
    result: list = []
    for seq in sequences:
        for item in seq or []:
            key = repr(item) if isinstance(item, dict) else item
            if key in seen:
                continue
            seen.add(key)
            result.append(item)
    return result


def merge_append_attr(
    base: list | None, specs: list[ListExtensionSpec], spec_attr: str
) -> list | None:
    """Union base list with values from spec.<spec_attr> across specs."""
    additions: list = []
    for spec in specs:
        additions.extend(getattr(spec, spec_attr, None) or [])
    if not additions and not base:
        return None
    merged = _union_sequence(list(base or []), additions)
    if merged == list(base or []) and not additions:
        return None
    return merged


def merge_scalar_overrides(specs: list[ListExtensionSpec]) -> dict:
    """Later specs (higher priority) override earlier scalar class attributes."""
    merged: dict = {}
    for spec in specs:
        merged.update(spec.scalar_overrides)
    return merged
