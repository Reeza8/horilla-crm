"""
mail services module
"""

# Standard library imports
import re

# Third-party imports (Django)
from django.conf import settings

from horilla.contrib.utils.middlewares import _thread_local
from horilla.urls import reverse

# First party imports (Horilla)
from horilla.utils import timezone

# Local imports
from .models import HorillaMail

_EMAIL_RE = re.compile(r"^[^@\s]+@([^@\s]+)$")


def _has_mx_record(domain: str) -> bool:
    """Return True if the domain can receive mail."""
    try:
        import dns.resolver

        try:
            answers = dns.resolver.resolve(domain, "MX")
            # Null MX (RFC 7505): single record with preference 0 and exchange "."
            # means the domain explicitly accepts no mail.
            records = list(answers)
            if len(records) == 1 and str(records[0].exchange).rstrip(".") == "":
                return False
            return True
        except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN):
            pass
        # Fallback: some domains use A records instead of MX
        try:
            dns.resolver.resolve(domain, "A")
            return True
        except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN):
            return False
    except Exception:
        return True  # If DNS lookup fails for any other reason, allow the send


def _find_undeliverable(recipients: list) -> list:
    """Return list of addresses whose domain has no MX/A record."""
    bad = []
    for addr in recipients:
        m = _EMAIL_RE.match(addr)
        if not m:
            bad.append(addr)
            continue
        domain = m.group(1)
        if not _has_mx_record(domain):
            bad.append(addr)
    return bad


class HorillaMailManager:
    """Service class to manage HorillaMail operations."""

    MAX_RETRIES = 3  # Optional retry limit

    @staticmethod
    def send_mail(mail: HorillaMail, context=None):
        """Send the given HorillaMail instance."""
        context = context or {}
        try:
            subject = mail.render_subject(context)
            body = mail.render_body(context)

            # Persist the rendered snapshot immediately so the preview always
            # shows exactly what was sent, regardless of who views it later.
            mail.rendered_subject = subject
            mail.rendered_body = body
            mail.save(update_fields=["rendered_subject", "rendered_body"])

            to = [
                email.strip() for email in (mail.to or "").split(",") if email.strip()
            ]
            cc = [
                email.strip() for email in (mail.cc or "").split(",") if email.strip()
            ]
            bcc = [
                email.strip() for email in (mail.bcc or "").split(",") if email.strip()
            ]

            if not to:
                raise ValueError("No recipient found in 'to' field")

            # Check MX records before attempting send — catches non-existent domains
            undeliverable = _find_undeliverable(to)
            if undeliverable:
                mail.mail_status = "bounced"
                mail.bounced_at = timezone.now()
                mail.mail_status_message = (
                    f"No mail server found for: {', '.join(undeliverable)}"
                )
                mail.save()
                return

            from django.core.mail import EmailMultiAlternatives, get_connection

            connection = get_connection(
                "horilla.contrib.mail.backends.HorillaDefaultMailBackend"
            )
            email = EmailMultiAlternatives(
                subject=subject,
                body=body,
                from_email=mail.sender.from_email if mail.sender else None,
                to=to,
                cc=cc,
                bcc=bcc,
                connection=connection,
            )

            # Inject tracking pixel so we can detect opens
            pixel_path = reverse(
                "mail:track_open", kwargs={"uid": str(mail.tracking_uid)}
            )
            site_url = getattr(settings, "SITE_URL", "").rstrip("/")
            if not site_url:
                request = getattr(_thread_local, "request", None)
                if request:
                    # Honour X-Forwarded-Host (set by ngrok / reverse proxies)
                    forwarded_host = request.META.get("HTTP_X_FORWARDED_HOST")
                    forwarded_proto = request.META.get(
                        "HTTP_X_FORWARDED_PROTO", "https"
                    )
                    if forwarded_host:
                        site_url = f"{forwarded_proto}://{forwarded_host}"
                    else:
                        site_url = request.build_absolute_uri("/").rstrip("/")
            pixel_tag = (
                f'<img src="{site_url}{pixel_path}" '
                f'width="1" height="1" style="display:none" alt="" />'
            )
            body = body + pixel_tag

            # Attach the HTML version
            email.attach_alternative(body, "text/html")

            for attachment in mail.attachments.filter(is_inline=True):
                # Standard library imports
                from email.mime.image import MIMEImage

                with attachment.file.open("rb") as f:
                    img_data = f.read()

                # Determine subtype from mime_type
                mime_type = attachment.mime_type or "image/jpeg"
                subtype = mime_type.split("/")[-1] if "/" in mime_type else "jpeg"

                img = MIMEImage(img_data, _subtype=subtype)
                img.add_header("Content-ID", f"<{attachment.content_id}>")
                img.add_header(
                    "Content-Disposition", "inline", filename=attachment.file_name()
                )
                email.attach(img)

            # Add regular file attachments
            for attachment in mail.attachments.filter(is_inline=False):
                email.attach(
                    attachment.file_name(),
                    attachment.file.read(),
                    attachment.mime_type or "application/octet-stream",
                )

            email.send()

            mail.mail_status = "delivered"
            mail.sent_at = timezone.now()
            mail.delivered_at = timezone.now()
            mail.mail_status_message = ""
            request = getattr(_thread_local, "request", None)
            if request:
                user = getattr(request, "user", None)
                if user and not user.is_anonymous:
                    mail.send_by = user
            mail.save()

        except Exception as e:
            import smtplib

            if isinstance(e, smtplib.SMTPRecipientsRefused):
                mail.mail_status = "bounced"
                mail.bounced_at = timezone.now()
                mail.mail_status_message = str(e)
            else:
                mail.mail_status = "failed"
                mail.mail_status_message = str(e)
            mail.save()
