"""Desktop detail view for the test model, as an app would declare one."""

# First party imports (Horilla)
from horilla.contrib.generics.views.details import HorillaDetailView

from .models import MobileTestRecord


class MobileTestRecordDetailView(HorillaDetailView):
    """Desktop detail page of ``MobileTestRecord`` with ``status`` as its stage bar."""

    model = MobileTestRecord
    body = ["name", "phone", "email", "city", "owner"]
    pipeline_field = "status"
