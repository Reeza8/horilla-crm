"""
Filters for the field requirements settings list.
"""

# First party imports (Horilla)
from horilla.contrib.generics.filters import HorillaFilterSet

# Local imports
from .models import FieldRequirement


class FieldRequirementFilter(HorillaFilterSet):
    """Filterset for FieldRequirement with search on the configured field."""

    class Meta:
        """Meta options for FieldRequirementFilter."""

        model = FieldRequirement
        fields = "__all__"
        exclude = ["additional_info"]
        search_fields = ["field_name"]
