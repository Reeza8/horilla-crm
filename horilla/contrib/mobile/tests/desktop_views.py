"""Desktop detail views for the test model, as an app would declare them."""

# First party imports (Horilla)
from horilla.contrib.generics.views.detail_tabs import HorillaDetailSectionView
from horilla.contrib.generics.views.details import HorillaDetailView

from .models import MobileTestRecord


class MobileTestRecordDetailView(HorillaDetailView):
    """Desktop detail page of ``MobileTestRecord`` with ``status`` as its stage bar."""

    model = MobileTestRecord
    body = ["name", "phone", "email", "city", "owner"]
    pipeline_field = "status"


class MobileTestRecordSectionView(HorillaDetailSectionView):
    """Desktop Details tab of ``MobileTestRecord``; Edit Details leaves the email alone."""

    model = MobileTestRecord
    non_editable_fields = ["email"]
