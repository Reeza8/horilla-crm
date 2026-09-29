"""
Template tags and filters for Horilla templates.

This package provides Django template filters and helper functions used across
Horilla templates. It is split into modules by concern; all tags are
registered on the single `register` so that {% load horilla_tags %} continues
to work unchanged.
"""

from ._registry import register

# Import submodules so they register their filters/tags on `register`.
from . import (
    action_tags,
    asset_tags,
    datetime_filters,
    display_tags,
    field_filters,
    history_display,
    history_i18n,
    icon_tags,
    misc_tags,
    navigation_tags,
    permission_tags,
    url_filters,
)

__all__ = ["register"]
