"""Feature registration for Review Process."""

# First party imports (Horilla)
from horilla.contrib.process.integration import (
    register_pre_approval_sync,
    register_suppress_approval_if,
)
from horilla.registry.feature import register_feature

# Local imports
from .utils import record_has_pending_review_jobs, refresh_review_jobs_for_record

register_feature(
    "reviews",
    "reviews_models",
    auto_register_all=False,
)


register_pre_approval_sync(refresh_review_jobs_for_record)
register_suppress_approval_if(record_has_pending_review_jobs)
