"""
Celery tasks for the Horilla mail system.

This module provides background tasks for:
- Sending scheduled emails at specified times
- Processing and queueing scheduled emails
- Sending emails asynchronously without blocking the main thread
- Fetching incoming mail from configured mailboxes into IncomingMail rows

Celery's autodiscover_tasks() only imports each app's tasks.py by
convention, so every task must live in this module (not a separate
incoming_tasks.py) to actually be registered with the worker.
"""

# Standard library imports
import base64
import email
import email.utils
import imaplib
import logging
import re
from datetime import datetime

# Third-party imports (Django)
import requests
from celery import shared_task
from django.core.files.base import ContentFile

from horilla.auth.models import User
from horilla.contrib.mail.fetch_hooks import (
    any_hook_reports_duplicate,
    resolve_fetch_hook_for_mailbox,
)
from horilla.contrib.mail.models import (
    DeletedIncomingMessageId,
    HorillaMailAttachment,
    HorillaMailConfiguration,
    IncomingMail,
)
from horilla.contrib.mail.views.outlook import refresh_outlook_token
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


@shared_task
def fetch_emails_to_incoming_mail():
    """
    Fetch today's emails from every configured incoming mailbox and persist
    them as IncomingMail rows (so the Inbox screen has data regardless of
    whether automatic Lead/Contact creation is configured). For any mailbox
    that also has a registered fetch hook's config (e.g. leads' EmailToLeadConfig),
    additionally apply its keyword/sender filters and auto-create a Lead or
    Contact per that hook.
    """

    mailboxes = HorillaMailConfiguration.objects.filter(
        mail_channel="incoming", is_active=True
    )

    if not mailboxes.exists():
        return {"status": "error", "message": "No email settings configured."}

    total_created = 0
    total_filtered = 0
    results = []

    for mail_config in mailboxes:
        try:
            hook, config = resolve_fetch_hook_for_mailbox(mail_config)
            if mail_config.type == "mail":
                created_count, filtered_count = fetch_from_imap(
                    mail_config, config, hook
                )
            elif mail_config.type == "outlook":
                created_count, filtered_count = fetch_from_outlook(
                    mail_config, config, hook
                )
            else:
                results.append(
                    {
                        "email": mail_config.username,
                        "error": f"Unknown mail type: {mail_config.type}",
                    }
                )
                continue

            total_created += created_count
            total_filtered += filtered_count
            results.append(
                {
                    "email": mail_config.username,
                    "created": created_count,
                    "filtered_by_keywords": filtered_count,
                }
            )

        except Exception as e:
            # logger.exception captures the full traceback, not just the
            # message - this task runs unattended every minute, so a
            # misconfigured mailbox (bad password, revoked OAuth grant) will
            # fail identically on every run; full tracebacks in the log are
            # the only diagnostic trail until this surfaces a proper
            # per-mailbox failure/alerting signal.
            logger.exception(
                "Error fetching emails for %s: %s", mail_config.username, e
            )
            results.append({"email": mail_config.username, "error": str(e)})

    return {
        "status": "success",
        "total_created": total_created,
        "total_filtered_by_keywords": total_filtered,
        "details": results,
    }


@shared_task
def prune_expired_deleted_message_ids():
    """
    Delete DeletedIncomingMessageId tombstones older than
    TOMBSTONE_RELEVANCE_WINDOW. A tombstone that old can no longer protect
    against anything, since the fetch task's own search window is far
    shorter than the window - so keeping it around would just grow the
    table forever for no benefit. See remember_deleted_message_id (signals.py)
    for where these rows get created.
    """
    from horilla.contrib.mail.models import TOMBSTONE_RELEVANCE_WINDOW

    cutoff = timezone.now() - TOMBSTONE_RELEVANCE_WINDOW
    deleted_count, _ = DeletedIncomingMessageId.objects.filter(
        deleted_at__lt=cutoff
    ).delete()
    return {"pruned": deleted_count}


def fetch_from_imap(mail_config, config, hook):
    """
    Fetch emails using IMAP for standard mail configurations.

    mail_config is the HorillaMailConfiguration to connect to (always present).
    config is the registered hook's per-mailbox config object, if any - used
    only to apply keyword/sender filters and decide whether to auto-create a
    Lead/Contact. Every fetched message is persisted as an IncomingMail row
    regardless.
    """
    # Respect the configured transport instead of always forcing
    # IMAP4_SSL: use_ssl means connect over SSL from the start (typically
    # port 993); otherwise connect plaintext and, if use_tls is set, upgrade
    # via STARTTLS before authenticating (typically port 143). A mailbox
    # genuinely configured for plaintext-then-STARTTLS would otherwise never
    # connect at all under a hardcoded IMAP4_SSL assumption.
    if mail_config.use_ssl:
        mail = imaplib.IMAP4_SSL(mail_config.host, mail_config.port)
    else:
        mail = imaplib.IMAP4(mail_config.host, mail_config.port)

    try:
        if not mail_config.use_ssl and mail_config.use_tls:
            mail.starttls()
        mail.login(mail_config.username, mail_config.get_decrypted_password())
        mail.select("inbox")

        # Get today's date in IMAP format
        today = datetime.now().strftime("%d-%b-%Y")
        result, data = mail.search(None, f"(SINCE {today})")

        email_ids = data[0].split()
        allowed_senders = hook["get_allowed_senders"](config) if hook and config else []
        created_count = 0
        filtered_count = 0

        for e_id in email_ids:
            try:
                _res, msg_data = mail.fetch(e_id, "(RFC822)")
                msg = email.message_from_bytes(msg_data[0][1])

                result = process_email_message(
                    msg, mail_config, config, allowed_senders, hook
                )
                if result == "created":
                    created_count += 1
                elif result == "filtered":
                    filtered_count += 1
            except Exception as exc:
                # One malformed/unprocessable message should not abort the
                # rest of this mailbox's batch for this run.
                logger.error(
                    "Error processing IMAP message %s for %s: %s",
                    e_id,
                    mail_config.username,
                    exc,
                )

        return created_count, filtered_count
    finally:
        try:
            mail.logout()
        except Exception:
            # Best-effort logout - the connection may already be dead (e.g.
            # the login itself failed), nothing further to clean up.
            pass


def fetch_from_outlook(mail_config, config, hook):
    """
    Fetch emails using Microsoft Graph API for Outlook configurations.

    mail_config is the HorillaMailConfiguration to connect to (always present).
    config is the registered hook's per-mailbox config object, if any - used
    only to apply keyword/sender filters and decide whether to auto-create a
    Lead/Contact. Every fetched message is persisted as an IncomingMail row
    regardless.
    """

    if not mail_config.token or "access_token" not in mail_config.token:
        raise ValueError("No valid access token found for Outlook configuration")

    access_token = mail_config.token["access_token"]

    # Get today's date in ISO 8601 format
    today = datetime.now().strftime("%Y-%m-%dT00:00:00Z")

    # Microsoft Graph API endpoint
    api_endpoint = (
        mail_config.outlook_api_endpoint or "https://graph.microsoft.com/v1.0"
    )
    url = f"{api_endpoint}/me/messages"

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    # Filter for today's emails
    params = {
        "$filter": f"receivedDateTime ge {today}",
        "$select": "id,subject,from,ccRecipients,body,bodyPreview,internetMessageId,internetMessageHeaders,hasAttachments",
        "$top": 100,
    }
    response = requests.get(url, headers=headers, params=params, timeout=30)

    # Auto-refresh token if expired
    if response.status_code == 401:
        mail_config = refresh_outlook_token(mail_config)

        # Retry with new token
        headers["Authorization"] = f"Bearer {mail_config.token['access_token']}"
        response = requests.get(url, headers=headers, params=params, timeout=30)

    response.raise_for_status()
    messages = response.json().get("value", [])

    allowed_senders = hook["get_allowed_senders"](config) if hook and config else []
    created_count = 0
    filtered_count = 0

    for msg in messages:
        try:
            result = process_outlook_message(
                msg, mail_config, config, allowed_senders, hook
            )
            if result == "created":
                created_count += 1
            elif result == "filtered":
                filtered_count += 1
        except Exception as exc:
            # One malformed/unprocessable message should not abort the rest
            # of this mailbox's batch for this run.
            logger.error(
                "Error processing Outlook message %s for %s: %s",
                msg.get("id"),
                mail_config.username,
                exc,
            )

    return created_count, filtered_count


def _create_record_from_hook(hook, config, incoming_mail):
    """
    Delegate auto-creation of a Lead/Contact (or whatever the registered
    hook implements) from a freshly persisted IncomingMail row. No-op if no
    hook is registered or this mailbox has no matching config - fetching and
    persisting to the Inbox still happens, just no automatic creation.
    """
    if not hook or not config:
        return
    hook["create_record"](config, incoming_mail)


def _save_incoming_attachment(
    incoming_mail, filename, content, content_id=None, is_inline=False
):
    """
    Save one attachment file against an already-persisted IncomingMail row.
    Shared by both the IMAP (raw MIME part bytes) and Outlook (base64-decoded
    Graph API attachment content) paths.

    is_inline must be derived from the message's actual Content-Disposition
    (or, for Outlook, its isInline flag) by the caller - a Content-ID header
    being present is not by itself a reliable signal, since some senders
    stamp one on ordinary file attachments too.
    """
    if not content:
        return
    HorillaMailAttachment.objects.create(
        incoming_mail=incoming_mail,
        file=ContentFile(content, name=filename or "attachment"),
        is_inline=is_inline,
        content_id=content_id,
        company=incoming_mail.company,
    )


def _resolve_inline_cid_images(incoming_mail):
    """
    Rewrite cid:<content-id> references in an HTML body to point at the
    actual saved inline attachment's URL, so inline images (logos, signature
    images) render where the email placed them instead of only appearing as
    a disconnected thumbnail list below the body.

    Must run after attachments are saved (it needs their file URLs), so this
    is a second pass over the already-persisted body - a one-off UPDATE, not
    something that reruns on every save().
    """
    if not incoming_mail.is_html_body or not incoming_mail.body:
        return
    inline_attachments = {
        attachment.content_id: attachment.file.url
        for attachment in incoming_mail.attachments.filter(
            is_inline=True, content_id__isnull=False
        )
        if attachment.content_id
    }
    if not inline_attachments:
        return

    def _replace_cid(match):
        content_id = match.group(1)
        return inline_attachments.get(content_id, match.group(0))

    new_body = re.sub(r'cid:([^"\'\s)]+)', _replace_cid, incoming_mail.body)
    if new_body != incoming_mail.body:
        incoming_mail.body = new_body
        incoming_mail.save(update_fields=["body"])


def _save_imap_attachments(msg, incoming_mail):
    """Extract and save any file attachments from a parsed IMAP message."""
    if not msg.is_multipart():
        return
    for part in msg.walk():
        content_disposition = part.get_content_disposition()
        if content_disposition not in ("attachment", "inline"):
            continue
        filename = part.get_filename()
        if not filename:
            continue
        content = part.get_payload(decode=True)
        content_id = part.get("Content-ID")
        if content_id:
            content_id = content_id.strip("<>")

        is_inline = content_disposition == "inline"
        _save_incoming_attachment(
            incoming_mail,
            filename,
            content,
            content_id if is_inline else None,
            is_inline=is_inline,
        )


def _save_outlook_attachments(mail_config, graph_item_id, incoming_mail):
    """
    Fetch and save file attachments for an Outlook message via Microsoft
    Graph API. The initial message-list response does not include attachment
    content, so this issues one extra request per message that has any.

    graph_item_id is the message's Graph "id" field - not the RFC internet
    Message-ID - since that's what the Graph attachments endpoint requires.
    """
    if not mail_config.token or "access_token" not in mail_config.token:
        return
    access_token = mail_config.token["access_token"]
    api_endpoint = (
        mail_config.outlook_api_endpoint or "https://graph.microsoft.com/v1.0"
    )
    url = f"{api_endpoint}/me/messages/{graph_item_id}/attachments"
    headers = {"Authorization": f"Bearer {access_token}"}

    try:
        response = requests.get(url, headers=headers, timeout=30)
        if response.status_code == 401:
            mail_config = refresh_outlook_token(mail_config)
            headers["Authorization"] = f"Bearer {mail_config.token['access_token']}"
            response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.error(
            "Error fetching Outlook attachments for message %s: %s",
            graph_item_id,
            exc,
        )
        return

    for attachment in response.json().get("value", []):
        if attachment.get("@odata.type") != "#microsoft.graph.fileAttachment":
            continue
        content_bytes = attachment.get("contentBytes")
        if not content_bytes:
            continue
        content = base64.b64decode(content_bytes)
        is_inline = bool(attachment.get("isInline"))
        _save_incoming_attachment(
            incoming_mail,
            attachment.get("name"),
            content,
            attachment.get("contentId") if is_inline else None,
            is_inline=is_inline,
        )


def _decode_part_payload(part):
    """
    Decode a MIME part's payload using its own declared charset, falling
    back to UTF-8 if none is declared, and to latin-1 (which never raises -
    every byte value maps to a character) as a last resort so content is
    substituted rather than silently dropped on a decode error. Using the
    wrong charset (or always assuming UTF-8) mangles any email from a sender
    using e.g. iso-8859-1, windows-1252, or a CJK encoding.
    """
    raw = part.get_payload(decode=True) or b""
    charset = part.get_content_charset() or "utf-8"
    try:
        return raw.decode(charset, errors="replace")
    except (LookupError, UnicodeDecodeError):
        return raw.decode("utf-8", errors="replace")


def _extract_imap_body(msg):
    """
    Extract the best available body from a parsed IMAP message.

    Prefers the text/html part (sanitized, so it can be rendered as real
    HTML in the preview, matching how the email actually looks) and falls
    back to text/plain only if no HTML part exists.
    Returns (body, is_html_body).
    """
    html_body = None
    plain_body = None

    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            if content_type == "text/html" and html_body is None:
                html_body = _decode_part_payload(part)
            elif content_type == "text/plain" and plain_body is None:
                plain_body = _decode_part_payload(part)
    else:
        payload = _decode_part_payload(msg)
        if msg.get_content_type() == "text/html":
            html_body = payload
        else:
            plain_body = payload

    if html_body is not None:
        return sanitize_html(html_body), True
    return plain_body or "", False


def process_email_message(msg, mail_config, config, allowed_senders, hook):
    """
    Process an email message from IMAP: always persist it as an IncomingMail
    row, and additionally create a Lead/Contact (or whatever the registered
    hook implements) if a matching per-mailbox config is provided.
    Returns: "created", "filtered", "skipped", or False
    """

    message_id = msg.get("Message-ID", "")

    if _is_duplicate_message([message_id]):
        return "skipped"

    in_reply_to = msg.get("In-Reply-To", "")
    references = msg.get("References", "")

    # Skip if this is a reply in an existing thread
    if check_existing_thread(in_reply_to, references):
        return "skipped"

    sender = email.utils.parseaddr(msg["From"])[1]
    sender_name = email.utils.parseaddr(msg["From"])[0]
    cc = msg.get("Cc", "")

    if allowed_senders and sender.lower() not in allowed_senders:
        return "skipped"

    subject = msg.get("Subject", "(No Subject)")
    body, is_html_body = _extract_imap_body(msg)

    # Content filters (e.g. keywords) only apply when this mailbox has a
    # registered hook's config.
    if config and hook and not hook["matches_filters"](config, subject, body):
        logger.info(
            "Email from %s filtered out by keywords. Subject: %s", sender, subject
        )
        return "filtered"

    incoming_mail, created = IncomingMail.objects.get_or_create(
        message_id=message_id,
        defaults={
            "mail": mail_config,
            "sender_email": sender,
            "sender_name": sender_name,
            "subject": subject,
            "body": body,
            "is_html_body": is_html_body,
            "cc": cc,
            "in_reply_to": in_reply_to,
            "references": references,
            "company": mail_config.company,
        },
    )
    if created:
        _save_imap_attachments(msg, incoming_mail)
        _resolve_inline_cid_images(incoming_mail)

    _create_record_from_hook(hook, config, incoming_mail)
    return "created"


def _format_outlook_recipients(recipients):
    """
    Format a Graph API recipient list (e.g. ccRecipients) into the same
    "Name <email>, Name <email>" comma-separated string shape the IMAP path
    gets for free from the raw Cc header, so IncomingMail.cc looks the same
    regardless of which fetch path populated it.
    """
    formatted = []
    for recipient in recipients or []:
        address = recipient.get("emailAddress", {})
        email_addr = address.get("address", "")
        name = address.get("name", "")
        if not email_addr:
            continue
        formatted.append(f"{name} <{email_addr}>" if name else email_addr)
    return ", ".join(formatted)


def process_outlook_message(msg, mail_config, config, allowed_senders, hook):
    """
    Process an Outlook message from Microsoft Graph API: always persist it as
    an IncomingMail row, and additionally create a Lead/Contact (or whatever
    the registered hook implements) if a matching per-mailbox config is
    provided. Returns: "created", "filtered", "skipped", or False
    """

    message_id = msg.get("internetMessageId", "")

    if _is_duplicate_message([message_id]):
        return "skipped"

    # Extract In-Reply-To and References from headers
    in_reply_to = ""
    references = ""
    headers = msg.get("internetMessageHeaders", [])
    for header in headers:
        if header.get("name") == "In-Reply-To":
            in_reply_to = header.get("value", "")
        elif header.get("name") == "References":
            references = header.get("value", "")

    # Skip if this is a reply in an existing thread
    if check_existing_thread(in_reply_to, references):
        return "skipped"

    sender = msg.get("from", {}).get("emailAddress", {}).get("address", "")
    sender_name = msg.get("from", {}).get("emailAddress", {}).get("name", "")
    cc = _format_outlook_recipients(msg.get("ccRecipients", []))

    if allowed_senders and sender.lower() not in allowed_senders:
        return "skipped"

    subject = msg.get("subject", "(No Subject)")

    # Get body content (prefer the full body, fallback to bodyPreview).
    # Graph API tells us whether body.content is "html" or "text" directly.
    body = ""
    is_html_body = False
    if msg.get("body"):
        body = msg["body"].get("content", "")
        is_html_body = msg["body"].get("contentType", "").lower() == "html"
    if not body:
        body = msg.get("bodyPreview", "")
        is_html_body = False
    elif is_html_body:
        body = sanitize_html(body)

    # Content filters (e.g. keywords) only apply when this mailbox has a
    # registered hook's config.
    if config and hook and not hook["matches_filters"](config, subject, body):
        logger.info(
            "Email from %s filtered out by keywords. Subject: %s", sender, sender
        )
        return "filtered"

    incoming_mail, created = IncomingMail.objects.get_or_create(
        message_id=message_id,
        defaults={
            "mail": mail_config,
            "sender_email": sender,
            "sender_name": sender_name,
            "subject": subject,
            "body": body,
            "is_html_body": is_html_body,
            "cc": cc,
            "in_reply_to": in_reply_to,
            "references": references,
            "company": mail_config.company,
        },
    )
    if created and msg.get("hasAttachments") and msg.get("id"):
        _save_outlook_attachments(mail_config, msg["id"], incoming_mail)
        _resolve_inline_cid_images(incoming_mail)

    _create_record_from_hook(hook, config, incoming_mail)
    return "created"


def _is_duplicate_message(message_ids):
    """
    True if any of the given RFC822 Message-IDs should not be (re)created:
    - the user explicitly deleted it from the Inbox before (see
      DeletedIncomingMessageId and signals.py's pre_delete receiver - this
      is what makes "delete" permanent even though the real mailbox still
      has the message and gets re-polled every minute), or
    - a registered fetch hook's is_duplicate_message reports it (see
      fetch_hooks.py's docstring for why that check exists alongside
      IncomingMail.message_id's own unique constraint, and why it checks
      across all registered hooks rather than just the mailbox's owning one).
    """
    message_ids = [m for m in message_ids if m]
    if not message_ids:
        return False
    if DeletedIncomingMessageId.objects.filter(message_id__in=message_ids).exists():
        return True
    return any_hook_reports_duplicate(message_ids)


def check_existing_thread(in_reply_to, references):
    """
    Check if email is part of an existing thread.

    Checks IncomingMail.message_id (this app's own dedup - a reply in a
    thread whose originating message is still here won't be reprocessed) and
    consults every registered fetch hook's is_duplicate_message, if any
    implement it. That hook exists for an edge case this app itself cannot
    see: e.g. leads keeps Lead.message_id around so a Lead created from an
    old email doesn't get reprocessed even if the originating IncomingMail
    row was since deleted. Without any registered hook (CRM off, or no hook
    implements it), dedup relies solely on IncomingMail.message_id's own
    unique constraint plus the references/in_reply_to lookups below - a
    simpler, acceptable behavior for the no-CRM case.
    """

    ref_ids = references.split() if references else []

    if _is_duplicate_message(([in_reply_to] if in_reply_to else []) + ref_ids):
        return True

    existing_mail = None
    if in_reply_to:
        existing_mail = IncomingMail.objects.filter(message_id=in_reply_to).first()
    if not existing_mail and ref_ids:
        existing_mail = IncomingMail.objects.filter(message_id__in=ref_ids).first()

    return existing_mail is not None
