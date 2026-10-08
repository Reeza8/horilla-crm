"""
mail signals module
"""

# Third-party imports (Django)
from django.dispatch import receiver

# First party imports (Horilla)
from horilla.db.models.signals import post_delete, pre_delete
from horilla.utils import timezone

# Local imports
from .models import (
    TOMBSTONE_RELEVANCE_WINDOW,
    DeletedIncomingMessageId,
    HorillaMailAttachment,
    IncomingMail,
)

# Define your mail signals here


@receiver(post_delete, sender=HorillaMailAttachment)
def auto_delete_file_on_delete(sender, instance, **kwargs):
    """Deletes file from storage when HorillaMailAttachment is deleted."""
    if instance.file:
        storage, path = instance.file.storage, instance.file.path
        if storage.exists(path):
            storage.delete(path)


@receiver(pre_delete, sender=IncomingMail)
def remember_deleted_message_id(sender, instance, **kwargs):
    """
    Record this message's Message-ID before the row (and its attachments,
    via cascade) are actually destroyed, so the fetch task's dedup check
    (tasks.py's _is_duplicate_message, consulted from get_or_create's
    defaults path) never recreates it even though the real mailbox still has
    the message. See DeletedIncomingMessageId's docstring for why this is a
    separate table rather than a soft-delete flag on IncomingMail itself.

    Only messages received within TOMBSTONE_RELEVANCE_WINDOW get a tombstone
    at all: an older message is already outside every fetch path's search
    window, so it can never be recreated regardless, and remembering it
    would just grow this table forever for no benefit. A periodic cleanup
    (prune_expired_deleted_message_ids, run from Celery beat) removes
    tombstones once they age past the same window, for the same reason.
    """
    if not instance.message_id:
        return
    if (
        instance.received_at
        and instance.received_at < timezone.now() - TOMBSTONE_RELEVANCE_WINDOW
    ):
        return
    DeletedIncomingMessageId.objects.get_or_create(message_id=instance.message_id)
