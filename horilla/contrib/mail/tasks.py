"""
Celery tasks for asynchronous email sending in the Horilla mail system.

This module provides background tasks for:
- Sending scheduled emails at specified times
- Processing and queueing scheduled emails
- Sending emails asynchronously without blocking the main thread
"""

# Standard library imports
import logging

# Third-party imports (Django)
from celery import shared_task

from horilla.auth.models import User
from horilla.contrib.utils.methods import sanitize_html, sanitize_plain_text
from horilla.contrib.utils.middlewares import _thread_local

# First party imports (Horilla)
from horilla.utils import timezone

logger = logging.getLogger(__name__)


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
def send_scheduled_mail_task(self, mail_id):
    """
    Celery task to send a scheduled mail using HorillaMailManager
    """

    # Local imports
    from .models import HorillaMail
    from .services import HorillaMailManager

    logger.info("Processing scheduled mail %s", mail_id)

    try:
        mail = HorillaMail.objects.get(pk=mail_id)

        # Check if mail is still in scheduled status
        if mail.mail_status != "scheduled":
            logger.info(
                "Mail %s status is %s, skipping send", mail_id, mail.mail_status
            )
            return f"Mail {mail_id} is not in scheduled status"

        # Check if scheduled time has arrived
        if mail.scheduled_at and mail.scheduled_at > timezone.now():
            logger.info("Mail %s scheduled time not yet reached", mail_id)
            return f"Mail {mail_id} not yet time to send"

        # Set thread local for from_mail_id to use correct configuration
        if mail.sender:
            setattr(_thread_local, "from_mail_id", mail.sender.pk)

        # Reconstruct context from additional_info
        request_info = (
            mail.additional_info.get("request_info", {}) if mail.additional_info else {}
        )

        # Get user and company
        user = mail.created_by
        company = mail.company

        # If user_id and company_id are stored in request_info, use them as fallback
        if not user and request_info.get("user_id"):
            try:
                user = User.objects.get(pk=request_info["user_id"])
            except User.DoesNotExist:
                pass

        if not company and request_info.get("company_id"):
            from horilla.contrib.core.models import Company

            try:
                company = Company.objects.get(pk=request_info["company_id"])
            except Company.DoesNotExist:
                pass

        # Create mock request object
        mock_request = MockRequest(user, company, request_info)
        setattr(_thread_local, "request", mock_request)

        # Prepare context for rendering
        context = {
            "instance": mail.related_to,
            "user": user,
            "active_company": company,
            "request": mock_request,
        }

        # Sanitize before rendering — strip dangerous content rather than aborting.
        if mail.subject:
            mail.subject = sanitize_plain_text(mail.subject)
        if mail.body:
            mail.body = sanitize_html(mail.body)

        # Use HorillaMailManager to send the mail
        HorillaMailManager.send_mail(mail, context=context)

        logger.info("Successfully sent mail %s", mail_id)
        return f"Successfully sent mail {mail_id}"

    except HorillaMail.DoesNotExist:
        logger.error("Mail %s does not exist", mail_id)
        return f"Mail {mail_id} not found"

    except ValueError as e:
        # Handle validation errors from HorillaMailManager
        logger.error("Validation error sending mail %s: %s", mail_id, str(e))

        try:
            mail = HorillaMail.objects.get(pk=mail_id)
            mail.mail_status = "failed"
            mail.mail_status_message = str(e)
            mail.save(update_fields=["mail_status", "mail_status_message"])
        except Exception:
            pass

        return f"Failed to send mail {mail_id}: {str(e)}"

    except Exception as e:
        logger.error("Error sending mail %s: %s", mail_id, str(e))

        try:
            mail = HorillaMail.objects.get(pk=mail_id)
            # HorillaMailManager already set status to failed
            # Only update if status is still scheduled
            if mail.mail_status == "scheduled":
                mail.mail_status = "failed"
                mail.mail_status_message = str(e)
                mail.save(update_fields=["mail_status", "mail_status_message"])
        except Exception:
            pass

        # Retry the task
        raise self.retry(exc=e, countdown=300)  # Retry after 5 minutes

    finally:
        # Clean up thread local
        if hasattr(_thread_local, "from_mail_id"):
            delattr(_thread_local, "from_mail_id")
        if hasattr(_thread_local, "request"):
            delattr(_thread_local, "request")


@shared_task
def refresh_outlook_auth_token():
    """
    Periodic task to refresh Outlook OAuth tokens.

    Celery Beat runs this on a single scheduler process, so unlike an
    in-process APScheduler job (which every worker would start a copy
    of) there is no risk of concurrent workers racing to refresh the
    same token. Microsoft rotates the refresh_token on every use, so
    a race would leave the loser with an invalid_client/invalid_grant
    error.
    """
    from .models import HorillaMailConfiguration
    from .views.outlook import refresh_outlook_token

    apis = HorillaMailConfiguration.objects.filter(token__isnull=False, type="outlook")
    for api in apis:
        try:
            refresh_outlook_token(api)
            logger.info("Updated token for %s outlook ", api)
        except Exception as e:
            logger.error("Error in refresh outlook token: %s", e)


@shared_task
def process_scheduled_mails():
    """
    Periodic task to check and queue scheduled mails for sending
    """
    from .models import HorillaMail

    # Get all scheduled mails whose time has arrived
    scheduled_mails = HorillaMail.objects.filter(
        mail_status="scheduled", scheduled_at__lte=timezone.now()
    )

    logger.info("Found %s scheduled mails to process", scheduled_mails.count())
    logger.info("Current time: %s", timezone.now())

    count = 0
    for mail in scheduled_mails:
        # Queue each mail for sending
        send_scheduled_mail_task.delay(mail.pk)
        count += 1

    logger.info("Queued %s scheduled mails for sending", count)
    return f"Queued {count} mails"


@shared_task
def send_mail_async(mail_id, context=None):
    """
    General purpose async task to send any mail immediately using HorillaMailManager
    """

    from .models import HorillaMail
    from .services import HorillaMailManager

    try:
        mail = HorillaMail.objects.get(pk=mail_id)

        # Set thread local if sender exists
        if mail.sender:
            setattr(_thread_local, "from_mail_id", mail.sender.pk)

        # If no context provided, try to reconstruct from additional_info
        if context is None:
            request_info = (
                mail.additional_info.get("request_info", {})
                if mail.additional_info
                else {}
            )

            user = mail.created_by
            company = mail.company

            if not user and request_info.get("user_id"):
                try:
                    user = User.objects.get(pk=request_info["user_id"])
                except User.DoesNotExist:
                    pass

            if not company and request_info.get("company_id"):
                from horilla.contrib.core.models import Company

                try:
                    company = Company.objects.get(pk=request_info["company_id"])
                except Company.DoesNotExist:
                    pass

            # Create mock request
            mock_request = MockRequest(user, company, request_info)
            setattr(_thread_local, "request", mock_request)

            context = {
                "instance": mail.related_to,
                "user": user,
                "self": user,  # 'self' refers to the user who triggered (for template compatibility)
                "active_company": company,
                "request": mock_request,
            }

        # Use HorillaMailManager to send
        HorillaMailManager.send_mail(mail, context=context)

        logger.info("Successfully sent mail %s asynchronously", mail_id)
        return f"Successfully sent mail {mail_id}"

    except HorillaMail.DoesNotExist:
        logger.error("Mail %s does not exist", mail_id)
        return f"Mail {mail_id} not found"

    except Exception as e:
        logger.error("Error sending mail %s: %s", mail_id, str(e), exc_info=True)
        # Try to update mail status
        try:
            mail = HorillaMail.objects.get(pk=mail_id)
            mail.mail_status = "failed"
            mail.mail_status_message = str(e)
            mail.save(update_fields=["mail_status", "mail_status_message"])
        except Exception:
            pass
        return f"Failed to send mail {mail_id}: {str(e)}"

    finally:
        # Clean up thread local
        if hasattr(_thread_local, "from_mail_id"):
            delattr(_thread_local, "from_mail_id")
        if hasattr(_thread_local, "request"):
            delattr(_thread_local, "request")

    return "Delivery failed"
