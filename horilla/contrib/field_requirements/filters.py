"""
Filters for the field requirements settings list.
"""

# Third-party imports (Django)
import django_filters

# First party imports (Horilla)
from horilla.contrib.core.models import HorillaContentType
from horilla.contrib.generics.filters import HorillaFilterSet

# Local imports
from .models import FieldRequirement
from .registry import limit_content_types


def _configurable_content_types(request):
    """Return opted-in models after CRM apps have registered them.

    django-filters snapshots a ForeignKey queryset when the FilterSet class is
    created. This app loads before Lead and Opportunity opt in, so capturing
    ``limit_content_types()`` then would freeze an empty list and Filter
    Records would show "No results found" for Model.
    """
    return HorillaContentType.objects.filter(limit_content_types()).order_by("pk")


class FieldRequirementFilter(HorillaFilterSet):
    """Filterset for FieldRequirement with search on the configured field."""

    content_type = django_filters.ModelChoiceFilter(
        queryset=_configurable_content_types,
        field_name="content_type",
    )

    class Meta:
        """Meta options for FieldRequirementFilter."""

        model = FieldRequirement
        fields = "__all__"
        exclude = ["additional_info"]
        search_fields = ["field_name"]
