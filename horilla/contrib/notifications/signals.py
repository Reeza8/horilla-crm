"""
Signal handlers for the notifications app.
"""

# Third party imports (Django Channels)
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

# Third-party imports (Django)
from django.dispatch import receiver

# First party imports (Horilla)
from horilla.db.models.signals import post_save
from horilla.urls import reverse

# Local imports
from .models import Notification


@receiver(post_save, sender=Notification)
def send_notification(sender, instance, created, **kwargs):
    """
    Sends real-time notification via Django Channels when a notification is created.
    """
    if not created:
        return
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    try:
        async_to_sync(channel_layer.group_send)(
            f"notifications_{instance.user.id}",  # User-specific group
            {
                "type": "notification_message",
                "message": instance.message,
                "created_at": instance.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                "sender": instance.sender.username if instance.sender else "System",
                "id": instance.id,
                "open_url": reverse(
                    "notifications:open_notification", args=[instance.id]
                ),
            },
        )
    except Exception:
        # Redis (or the configured channel backend) may be down in local/test
        # environments; never fail the Notification save because of that.
        import logging

        logging.getLogger(__name__).exception(
            "Failed to push notification %s over channels", instance.id
        )
