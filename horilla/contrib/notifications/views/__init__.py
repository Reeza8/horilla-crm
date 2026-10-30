"""Aggregate view modules for the `notifications.views` package."""

from horilla.contrib.notifications.views.core import (
    MarkNotificationReadView,
    MarkAllNotificationsReadView,
    DeleteNotification,
    DeleteAllNotification,
    OpenNotificationView,
    ToggleNotificationSoundView,
)
from horilla.contrib.notifications.views.notification_template import (
    NotificationTemplateView,
    NotificationTemplateNavbar,
    NotificationTemplateListView,
    NotificationTemplateCreateUpdateView,
    NotificationTemplateDeleteView,
    NotificationTemplateDetailView,
)

__all__ = [
    # Core Views
    "MarkNotificationReadView",
    "MarkAllNotificationsReadView",
    "DeleteNotification",
    "DeleteAllNotification",
    "OpenNotificationView",
    "ToggleNotificationSoundView",
    # Notification Template Views
    "NotificationTemplateView",
    "NotificationTemplateNavbar",
    "NotificationTemplateListView",
    "NotificationTemplateCreateUpdateView",
    "NotificationTemplateDeleteView",
    "NotificationTemplateDetailView",
]
