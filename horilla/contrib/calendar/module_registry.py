"""Helpers for the ``custom_calendar_models`` feature registry (used by forms, not registration.py)."""

# First party imports (Horilla)
from horilla.registry.feature import FEATURE_REGISTRY


def get_custom_calendar_models():
    """``[(module_key, model_cls), ...]`` — same shape as dashboard component helpers."""
    out = []
    for model_cls in FEATURE_REGISTRY.get("custom_calendar_models", []):
        out.append((model_cls.__name__.lower(), model_cls))
    return out
