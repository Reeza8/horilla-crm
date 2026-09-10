"""
Celery tasks for asynchronous score recalculation in the scoring_rules app.
"""

# Standard library imports
import logging

# Third-party imports (Django)
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def recalculate_scores_for_module_task(self, module):
    """
    Celery task to recalculate scores for all instances of a module
    based on active scoring rules.

    Args:
        module: String (e.g., 'lead', 'opportunity') indicating the module.
    """
    # Imported lazily to avoid circular imports between signals and tasks.
    from horilla_crm.scoring_rules.signals import update_all_scores_for_module

    try:
        update_all_scores_for_module(module)
        logger.info("Recalculated scores for module %s", module)
        return f"Scores recalculated for module {module}"
    except Exception as e:
        logger.error(
            "Error recalculating scores for module %s: %s", module, e, exc_info=True
        )
        try:
            raise self.retry(exc=e, countdown=60)
        except Exception as retry_error:
            logger.error("Failed to retry task: %s", retry_error)
            return f"Task failed and retry failed: {str(e)}"
