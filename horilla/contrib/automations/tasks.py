"""
Celery tasks for asynchronous automation execution in the Horilla automations system.

This module provides background tasks for:
- Executing automations asynchronously without blocking the main thread
- Sending emails and notifications in the background
- Running time-based (scheduled) automations across all modules
"""

# Standard library imports
import logging
from datetime import timedelta

# Third-party imports (Django)
from celery import shared_task
from dateutil.relativedelta import relativedelta
from django.db import models

from horilla.auth.models import User
from horilla.contrib.core.models import Company, HorillaContentType
from horilla.contrib.utils.middlewares import _thread_local

# First party imports (Horilla)
from horilla.utils import timezone

from .methods import (
    evaluate_automation_conditions,
    execute_automation,
    trigger_automations,
)

# Local imports
from .models import AutomationRunLog, HorillaAutomation

logger = logging.getLogger(__name__)


def _localtime_for_automation(dt, automation):
    """Convert a UTC-aware datetime using created_by.time_zone -> company.time_zone -> UTC."""
    if dt is None:
        return dt
    try:
        from zoneinfo import ZoneInfo

        tz_name = getattr(automation.created_by, "time_zone", None) or getattr(
            automation.company, "time_zone", None
        )
        if tz_name:
            return dt.astimezone(ZoneInfo(tz_name))
    except Exception:
        pass
    return dt  # return as-is (UTC) rather than silently wrong local time


class MockRequest:
    """Mock request object for Celery tasks"""

    def __init__(self, user, company, request_info):
        """
        Initialize a mock request object for use in Celery tasks.

        Args:
            user: The user associated with the request
            company: The active company for the request
            request_info: Dictionary containing request metadata (meta, host, scheme)
        """
        self.user = user
        self.active_company = company
        self.META = request_info.get("meta", {})
        self._host = request_info.get("host", "")
        self.scheme = request_info.get("scheme", "https")
        self.is_anonymous = user is None

    def get_host(self):
        """Get host for use in templates"""
        return self._host

    def build_absolute_uri(self, location=None):
        """Build absolute URI for use in templates"""
        if location is None:
            return f"{self.scheme}://{self._host}/"
        if location.startswith("http"):
            return location
        return f"{self.scheme}://{self._host}{location}"


@shared_task(bind=True, max_retries=3)
def execute_automation_task(
    self,
    content_type_id,
    object_id,
    trigger_type,
    user_id=None,
    company_id=None,
    request_info=None,
):
    """
    Celery task to execute automations asynchronously.

    Args:
        content_type_id: ID of the HorillaContentType for the instance
        object_id: ID of the instance that triggered the automation
        trigger_type: Type of trigger ('on_create', 'on_update', 'on_delete')
        user_id: ID of the user who triggered the automation (optional)
        company_id: ID of the company (optional)
        request_info: Dictionary containing request metadata (optional)
    """
    try:
        # Get the content type and instance
        content_type = HorillaContentType.objects.get(pk=content_type_id)
        model_class = content_type.model_class()

        if not model_class:
            logger.error(
                "Model class not found for content_type_id %s", content_type_id
            )
            return f"Model class not found for content_type_id {content_type_id}"

        # Get the instance
        # For delete triggers, the instance may already be deleted, which is OK
        instance = None
        try:
            instance = model_class.objects.get(pk=object_id)
        except model_class.DoesNotExist:
            if trigger_type == "on_delete":
                # For delete triggers, the instance is already deleted
                # We'll still try to execute automations, but condition evaluation will be skipped
                logger.info(
                    "Instance %s of %s already deleted, proceeding with delete automation",
                    object_id,
                    model_class.__name__,
                )
            else:
                logger.warning(
                    "Instance %s of %s not found, skipping automation",
                    object_id,
                    model_class.__name__,
                )
                return f"Instance {object_id} not found"

        # Get user if provided
        user = None
        if user_id:
            try:
                user = User.objects.get(pk=user_id)
            except User.DoesNotExist:
                logger.warning("User %s not found", user_id)

        # Get company if provided
        company = None
        if company_id:
            try:
                company = Company.objects.get(pk=company_id)
            except Company.DoesNotExist:
                logger.warning("Company %s not found", company_id)

        # Set up thread local for context
        request_info = request_info or {}
        mock_request = MockRequest(user, company, request_info)
        setattr(_thread_local, "request", mock_request)

        try:
            if instance is None and trigger_type == "on_delete":
                automations = HorillaAutomation.objects.filter(
                    model=content_type, trigger="on_delete"
                )
                for automation in automations:
                    try:
                        minimal_instance = type(
                            "DeletedInstance",
                            (),
                            {
                                "pk": object_id,
                                "_meta": model_class._meta,
                                "__str__": lambda self: (
                                    f"Deleted {model_class.__name__} {object_id}"
                                ),
                            },
                        )()
                        # Execute without condition check for delete
                        execute_automation(
                            automation, minimal_instance, user, trigger_type
                        )
                    except Exception as e:
                        logger.error(
                            "Error executing delete automation %s : %s",
                            automation.title,
                            str(e),
                            exc_info=True,
                        )
            else:
                trigger_automations(instance, trigger_type=trigger_type, user=user)

            logger.info(
                "Successfully executed automations for %s (id=%s, trigger=%s)",
                model_class.__name__,
                object_id,
                trigger_type,
            )
            return f"Automations executed for {model_class.__name__} {object_id}"

        finally:
            # Clean up thread local
            if hasattr(_thread_local, "request"):
                delattr(_thread_local, "request")

    except Exception as e:
        logger.error(
            "Error executing automation task for %s (content_type_id=%s, object_id=%s ): %s",
            trigger_type,
            content_type_id,
            object_id,
            str(e),
            exc_info=True,
        )
        # Don't retry for certain errors (like instance not found)
        if "not found" in str(e).lower() or "DoesNotExist" in str(type(e).__name__):
            logger.warning("Skipping retry for non-retryable error: %s", str(e))
            return f"Task failed: {str(e)}"
        # Retry on other failures
        try:
            raise self.retry(exc=e, countdown=60)
        except Exception as retry_error:
            logger.error("Failed to retry task: %s", retry_error)
            return f"Task failed and retry failed: {str(e)}"
        # Note: raise self.retry() will cause Celery to retry the task,
        # so this function will be called again. The return below ensures
        # all code paths that complete normally return a value.
        return f"Task failed: {str(e)}"


@shared_task
def run_scheduled_automations():
    """
    Scan and execute all due scheduled automations.

    How it works:
    - Looks for automations with trigger='scheduled'
    - For each automation:
      - Resolve "today"/"current time" in the automation's own timezone:
        created_by.time_zone, falling back to company.time_zone, then UTC
      - If schedule_run_time is set, skip until that local time passes
      - Compute the target date: today + (offset sign applied)
      - Find instances whose automation.schedule_date_field == target date
      - Evaluate automation conditions
      - Execute automation with trigger_type='scheduled'
      - Record an AutomationRunLog to prevent duplicates
    Run this task periodically (e.g., hourly or daily) via Celery Beat.
    """
    now = timezone.now()

    logger.info("=== run_scheduled_automations started at %s ===", now)

    automations = HorillaAutomation.objects.filter(trigger="scheduled", is_active=True)

    logger.info("Found %s scheduled automations", automations.count())

    for automation in automations:
        try:
            content_type = automation.model
            model_class = content_type.model_class()
            if not model_class:
                logger.warning("Model class not found for automation %s", automation.id)
                continue

            # Evaluate "today" and "current time" in the automation owner's
            # timezone (falling back to company, then UTC) so Run Time is
            # compared like-for-like with what the user entered.
            local_now = _localtime_for_automation(now, automation)
            today = local_now.date()
            current_time = local_now.time()

            # If a preferred run time is set, skip until that time passes
            if (
                automation.schedule_run_time
                and current_time < automation.schedule_run_time
            ):
                logger.info(
                    "Skipping automation %s until %s",
                    automation.id,
                    automation.schedule_run_time,
                )
                continue

            # Determine target date based on offset and direction
            offset_amount = automation.schedule_offset_amount or 0
            direction = automation.schedule_offset_direction or "before"
            unit = automation.schedule_offset_unit or "days"

            if unit == "months":
                delta = relativedelta(months=offset_amount)
            elif unit == "weeks":
                delta = timedelta(weeks=offset_amount)
            else:
                delta = timedelta(days=offset_amount)

            # We match instances whose date_field equals the computed date for "run today":
            # - direction='before': run N units before date_field => date_field = today + delta
            # - direction='after' : run N units after date_field => date_field = today - delta
            target_date = today + delta if direction == "before" else today - delta

            # Build queryset: instances where date_field == target_date
            date_field = automation.schedule_date_field
            if not date_field:
                logger.warning(
                    "Automation %s missing schedule_date_field, skipping", automation.id
                )
                continue

            try:
                # Validate field exists on model
                field = model_class._meta.get_field(date_field)
            except Exception:
                logger.error(
                    "Automation %s references unknown field '%s' on %s",
                    automation.id,
                    date_field,
                    model_class.__name__,
                )
                continue

            # DateTimeFields need a __date lookup to match on calendar date only;
            # an exact match against a date object would only hit midnight values.
            if isinstance(field, models.DateTimeField):
                filter_kwargs = {f"{date_field}__date": target_date}
            else:
                filter_kwargs = {f"{date_field}": target_date}
            queryset = model_class.objects.filter(**filter_kwargs)

            logger.info(
                "Automation %s targeting %s instances for date %s",
                automation.id,
                queryset.count(),
                target_date,
            )

            for instance in queryset:
                # Prevent duplicates for the same instance and scheduled target date.
                # This allows re-running if the instance's date field changes.
                if AutomationRunLog.objects.filter(
                    automation=automation,
                    content_type=content_type,
                    object_id=str(instance.pk),
                    scheduled_for=target_date,
                ).exists():
                    continue

                # Evaluate conditions using existing engine
                try:
                    if not evaluate_automation_conditions(automation, instance):
                        continue
                except Exception as e:
                    logger.error(
                        "Condition evaluation failed for automation %s on %s(%s): %s",
                        automation.id,
                        model_class.__name__,
                        instance.pk,
                        e,
                        exc_info=True,
                    )
                    continue

                # Execute with trigger_type='scheduled'
                try:
                    execute_automation(
                        automation, instance, user=None, trigger_type="scheduled"
                    )
                except Exception as e:
                    logger.error(
                        "Execution failed for automation %s on %s(%s): %s",
                        automation.id,
                        model_class.__name__,
                        instance.pk,
                        e,
                        exc_info=True,
                    )
                    continue

                AutomationRunLog.objects.create(
                    automation=automation,
                    content_type=content_type,
                    object_id=str(instance.pk),
                    run_date=today,
                    scheduled_for=target_date,
                    company=getattr(instance, "company", None)
                    or getattr(automation, "company", None),
                )

        except Exception as e:
            logger.error(
                "Error processing scheduled automation %s: %s",
                automation.id,
                e,
                exc_info=True,
            )

    logger.info("=== run_scheduled_automations completed ===")
    return "Scheduled automations processed"
