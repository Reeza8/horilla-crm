"""
URL configuration for notifications app.

This module defines URL patterns for notification-related views, including:
- Marking notifications as read (single or all)
- Deleting notifications (single or all)
- Opening/redirecting to notification URLs
"""

# First party imports (Horilla)
from horilla.urls import path

# Local imports
from . import views

app_name = "notifications"

urlpatterns = [
    path(
        "notifications-read/<int:pk>/",
        views.MarkNotificationReadView.as_view(),
        name="mark_read",
    ),
    path(
        "notifications-all-read/",
        views.MarkAllNotificationsReadView.as_view(),
        name="mark_all_read",
    ),
    path(
        "notification-delete/<int:pk>/",
        views.DeleteNotification.as_view(),
        name="notification_delete",
    ),
    path(
        "notification-all-delete/",
        views.DeleteAllNotification.as_view(),
        name="notification_all_delete",
    ),
    path(
        "open-notification/<int:pk>/",
        views.OpenNotificationView.as_view(),
        name="open_notification",
    ),
    path(
        "notification-sound-toggle/",
        views.ToggleNotificationSoundView.as_view(),
        name="toggle_sound",
    ),
    # Notification Template Urls
    path(
        "notification-template-view/",
        views.NotificationTemplateView.as_view(),
        name="notification_template_view",
    ),
    path(
        "notification-template-nav-view/",
        views.NotificationTemplateNavbar.as_view(),
        name="notification_template_nav_view",
    ),
    path(
        "notification-template-list-view/",
        views.NotificationTemplateListView.as_view(),
        name="notification_template_list_view",
    ),
    path(
        "notification-template-detail-view/<int:pk>/",
        views.NotificationTemplateDetailView.as_view(),
        name="notification_template_detail_view",
    ),
    path(
        "notification-template-create-view/",
        views.NotificationTemplateCreateUpdateView.as_view(),
        name="notification_template_create_view",
    ),
    path(
        "notification-template-update-view/<int:pk>/",
        views.NotificationTemplateCreateUpdateView.as_view(),
        name="notification_template_update_view",
    ),
    path(
        "notification-template-delete-view/<int:pk>/",
        views.NotificationTemplateDeleteView.as_view(),
        name="notification_template_delete_view",
    ),
]
