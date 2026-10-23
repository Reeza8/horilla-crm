"""
URL patterns for the mobile app (mounted under /m/).
"""

# First party imports (Horilla)
from horilla.urls import path

# Local imports
from . import details, log_activity, records, today, views

app_name = "mobile"

urlpatterns = [
    path("", views.MobileHomeView.as_view(), name="home"),
    path("login/", views.MobileLoginView.as_view(), name="login"),
    path("logout/", views.MobileLogoutView.as_view(), name="logout"),
    path("today/", today.MobileTodayView.as_view(), name="today"),
    path(
        "activities/<int:pk>/status/",
        today.MobileActivityStatusView.as_view(),
        name="activity_status",
    ),
    path("records/", records.MobileRecordsView.as_view(), name="records"),
    path(
        "records/<str:app_label>/<str:model_name>/<int:pk>/",
        records.MobileRecordView.as_view(),
        name="record",
    ),
    path(
        "records/<str:app_label>/<str:model_name>/<int:record_pk>/note/",
        log_activity.MobileNoteView.as_view(),
        name="add_note",
    ),
    path(
        "records/<str:app_label>/<str:model_name>/<int:record_pk>/log/<str:kind>/",
        log_activity.MobileLogActivityView.as_view(),
        name="log_activity",
    ),
    path(
        "activities/<int:pk>/",
        details.MobileActivityDetailView.as_view(),
        name="activity_detail",
    ),
    path(
        "activities/<int:pk>/edit/",
        log_activity.MobileEditActivityView.as_view(),
        name="edit_activity",
    ),
    path("notes/<int:pk>/", details.MobileNoteDetailView.as_view(), name="note_detail"),
    path(
        "notes/<int:pk>/edit/",
        log_activity.MobileEditNoteView.as_view(),
        name="edit_note",
    ),
    path("more/", views.MobileMoreView.as_view(), name="more"),
    path("manifest.webmanifest", views.ManifestView.as_view(), name="manifest"),
    path("sw.js", views.ServiceWorkerView.as_view(), name="service_worker"),
]
