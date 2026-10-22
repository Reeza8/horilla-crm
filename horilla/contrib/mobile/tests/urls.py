"""
URLconf for the record-page tests: the project URLs plus the desktop detail
page of the test model.
"""

# First party imports (Horilla)
from horilla.urls import path
from horilla.urls.project import urlpatterns as project_urlpatterns

from .desktop_views import MobileTestRecordDetailView

urlpatterns = [
    *project_urlpatterns,
    path(
        "mobile-tests/records/<int:pk>/",
        MobileTestRecordDetailView.as_view(),
        name="mobile_test_record_detail",
    ),
]
