"""
URL patterns for the mobile app (mounted under /m/).
"""

# First party imports (Horilla)
from horilla.urls import path

# Local imports
from . import records, views

app_name = "mobile"

urlpatterns = [
    path("", views.MobileHomeView.as_view(), name="home"),
    path("login/", views.MobileLoginView.as_view(), name="login"),
    path("logout/", views.MobileLogoutView.as_view(), name="logout"),
    path("records/", records.MobileRecordsView.as_view(), name="records"),
    path(
        "records/<str:app_label>/<str:model_name>/<int:pk>/",
        records.MobileRecordView.as_view(),
        name="record",
    ),
    path("more/", views.MobileMoreView.as_view(), name="more"),
    path("manifest.webmanifest", views.ManifestView.as_view(), name="manifest"),
    path("sw.js", views.ServiceWorkerView.as_view(), name="service_worker"),
]
