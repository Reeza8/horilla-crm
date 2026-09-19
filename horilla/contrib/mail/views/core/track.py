"""
Tracking pixel view for email open detection.
"""

# Third-party imports (Django)

# First party imports (Horilla)
from horilla.utils import timezone
from horilla.views.generic import View
from horilla.web import HttpResponse

# Local imports
from ...models import HorillaMail

# 1×1 transparent GIF
_PIXEL_GIF = (
    b"\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00"
    b"\xff\xff\xff\x00\x00\x00\x21\xf9\x04\x00\x00\x00\x00\x00"
    b"\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02\x44\x01\x00\x3b"
)


class TrackOpenView(View):
    """Returns a 1×1 pixel GIF and marks the mail as opened on first load."""

    def get(self, request, uid, *args, **kwargs):
        """Mark the mail open on first request and respond with a transparent GIF."""
        mail = HorillaMail.objects.filter(tracking_uid=uid).first()
        if mail and mail.opened_at is None:
            mail.opened_at = timezone.now()
            mail.mail_status = "opened"
            mail.save(update_fields=["opened_at", "mail_status", "updated_at"])
        return HttpResponse(_PIXEL_GIF, content_type="image/gif")
