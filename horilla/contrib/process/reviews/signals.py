"""Signals for review job creation."""

# Standard library imports
import logging

# First party imports (Horilla)
from horilla.db.models.signals import post_save, pre_save
from horilla.registry.feature import FEATURE_CONFIG, FEATURE_REGISTRY

# Local imports
from .utils import capture_review_save_context, sync_jobs_for_record

logger = logging.getLogger(__name__)


def reviews_pre_save_handler(sender, instance, **kwargs):
    """Record whether this save is a create and which reviewed fields changed."""
    if kwargs.get("raw"):
        return
    registry_key = FEATURE_CONFIG.get("reviews", "reviews_models")
    if sender not in FEATURE_REGISTRY.get(registry_key, []):
        return
    try:
        capture_review_save_context(instance, kwargs.get("update_fields"))
    except Exception:
        logger.exception("Failed to capture review save context for %s", instance)


def reviews_post_save_handler(sender, instance, **kwargs):
    """Sync review jobs for a record after it is saved.

    Registry membership is checked at dispatch time so that app loading order
    does not matter — the `reviews` app initialises before other apps, but
    FEATURE_REGISTRY is fully populated by the time any real request triggers
    a model save.
    """
    registry_key = FEATURE_CONFIG.get("reviews", "reviews_models")
    if sender not in FEATURE_REGISTRY.get(registry_key, []):
        return
    try:
        sync_jobs_for_record(instance)
    except Exception:
        logger.exception("Failed to sync review jobs for %s", instance)


# Connect a single global handler.  Per-model connections attempted at app
# startup fail silently because target apps register their models AFTER the
# reviews app's ready() runs, leaving the registry empty at that point.
post_save.connect(
    reviews_post_save_handler,
    dispatch_uid="reviews_post_save_global",
)

pre_save.connect(
    reviews_pre_save_handler,
    dispatch_uid="reviews_pre_save_global",
)
