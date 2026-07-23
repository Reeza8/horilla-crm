"""
Filtering utilities for horilla.contrib.generics.

Provides the HorillaFilterSet and operator choices used by generic filtering forms.
"""

# Standard library imports
import logging
from calendar import monthrange
from datetime import timedelta

# Third-party imports (Others)
import django_filters
from django.utils import timezone

# First party imports (Horilla)
from horilla.db import models
from horilla.db.models import Q
from horilla.utils.translation import gettext_lazy as _

# String-like field types where "empty" means NULL or empty string
STRING_LIKE_FIELDS = (
    models.CharField,
    models.TextField,
    models.EmailField,
    models.URLField,
    models.GenericIPAddressField,
    models.SlugField,
)

# Relative date operators that do not require a value input
RELATIVE_DATE_OPERATORS = ("today", "yesterday", "this_week", "this_month")


logger = logging.getLogger(__name__)
# Define operator choices by field type
OPERATOR_CHOICES = {
    "text": [
        ("icontains", _("Contains")),
        ("exact", _("Equals")),
        ("ne", _("Not Equals")),
        ("istartswith", _("Starts with")),
        ("iendswith", _("Ends with")),
        ("isnull", _("Is empty")),
        ("isnotnull", _("Is not empty")),
    ],
    "number": [
        ("exact", _("Equals")),
        ("gt", _("Greater than")),
        ("lt", _("Less than")),
        ("gte", _("Greater than or equal")),
        ("lte", _("Less than or equal")),
        ("between", _("Between")),
        ("isnull", _("Is empty")),
        ("isnotnull", _("Is not empty")),
    ],
    "float": [
        ("exact", _("Equals")),
        ("gt", _("Greater than")),
        ("lt", _("Less than")),
        ("gte", _("Greater than or equal")),
        ("lte", _("Less than or equal")),
        ("between", _("Between")),
        ("isnull", _("Is empty")),
        ("isnotnull", _("Is not empty")),
    ],
    "decimal": [
        ("exact", _("Equals")),
        ("gt", _("Greater than")),
        ("lt", _("Less than")),
        ("gte", _("Greater than or equal")),
        ("lte", _("Less than or equal")),
        ("between", _("Between")),
        ("isnull", _("Is empty")),
        ("isnotnull", _("Is not empty")),
    ],
    "date": [
        ("exact", _("Equals")),
        ("gt", _("After")),
        ("lt", _("Before")),
        ("between", _("Between")),
        ("today", _("Today")),
        ("yesterday", _("Yesterday")),
        ("this_week", _("This Week")),
        ("this_month", _("This Month")),
        ("isnull", _("Is empty")),
        ("isnotnull", _("Is not empty")),
    ],
    "datetime": [
        ("exact", _("Equals")),
        ("gt", _("After")),
        ("lt", _("Before")),
        ("between", _("Between")),
        ("today", _("Today")),
        ("yesterday", _("Yesterday")),
        ("this_week", _("This Week")),
        ("this_month", _("This Month")),
        ("isnull", _("Is empty")),
        ("isnotnull", _("Is not empty")),
    ],
    "boolean": [("exact", _("Equals"))],
    "choice": [
        ("exact", _("Equals")),
        ("isnull", _("Is empty")),
        ("isnotnull", _("Is not empty")),
    ],
    "other": [
        ("exact", _("Equals")),
        ("icontains", _("Contains")),
        ("isnull", _("Is empty")),
        ("isnotnull", _("Is not empty")),
    ],
}


class HorillaFilterSet(django_filters.FilterSet):
    """
    Custom FilterSet for Horilla with enhanced search and filtering capabilities.

    Provides field-type-specific operators and boolean value conversion
    for generic filtering across Horilla models.
    """

    search = django_filters.CharFilter(method="filter_search", label="Search")

    @classmethod
    def get_operators_for_field(cls, field_type):
        """Return appropriate operators for a given field type"""
        return OPERATOR_CHOICES.get(field_type, OPERATOR_CHOICES["other"])

    def _get_relative_date_bounds(self, operator):
        """
        Return (start_date, end_date) inclusive bounds for relative date operators.
        Week starts on Monday.
        """
        today = timezone.localdate()
        if operator == "today":
            return today, today
        if operator == "yesterday":
            yesterday = today - timedelta(days=1)
            return yesterday, yesterday
        if operator == "this_week":
            week_start = today - timedelta(days=today.weekday())
            week_end = week_start + timedelta(days=6)
            return week_start, week_end
        if operator == "this_month":
            month_start = today.replace(day=1)
            last_day = monthrange(today.year, today.month)[1]
            month_end = today.replace(day=last_day)
            return month_start, month_end
        return None, None

    def _apply_relative_date_filter(self, queryset, field, operator):
        """Apply today/yesterday/this_week/this_month filters for date/datetime fields."""
        start_date, end_date = self._get_relative_date_bounds(operator)
        if start_date is None:
            return queryset

        model = queryset.model
        try:
            field_obj = model._meta.get_field(field.split("__")[0])
        except (models.FieldDoesNotExist, AttributeError):
            field_obj = None

        # DateTimeField is a subclass of DateField — check DateTimeField first
        if field_obj is not None and isinstance(field_obj, models.DateTimeField):
            if start_date == end_date:
                return queryset.filter(**{f"{field}__date": start_date})
            return queryset.filter(
                **{f"{field}__date__gte": start_date, f"{field}__date__lte": end_date}
            )

        if start_date == end_date:
            return queryset.filter(**{field: start_date})
        return queryset.filter(
            **{f"{field}__gte": start_date, f"{field}__lte": end_date}
        )

    def _convert_boolean_value(self, value, model, field_name):
        """Convert boolean string values to proper format for filtering"""
        if value is None:
            return None

        # Check if the field is a BooleanField
        try:
            field = model._meta.get_field(field_name)
            if isinstance(field, models.BooleanField):
                # Convert lowercase "true"/"false" to proper boolean or capitalized string
                value_str = str(value).lower()
                return {"true": True, "false": False}.get(value_str)

        except (models.FieldDoesNotExist, AttributeError):
            pass

        return value

    def filter_queryset(self, queryset):
        """
        Override the default filter_queryset to handle our custom filtering approach.
        Process arrays of fields, operators, and values.
        """
        if hasattr(self, "form") and hasattr(self.form, "cleaned_data"):
            queryset = super().filter_queryset(queryset)

        request = getattr(self, "request", None)
        if not request and hasattr(self, "data") and hasattr(self.data, "_request"):
            request = self.data._request

        if not request:
            return queryset

        fields = self.data.getlist("field", []) or request.GET.getlist("field", [])
        operators = self.data.getlist("operator", []) or request.GET.getlist(
            "operator", []
        )
        values = self.data.getlist("value", []) or request.GET.getlist("value", [])
        start_values = self.data.getlist("start_value", []) or request.GET.getlist(
            "start_value", []
        )
        end_values = self.data.getlist("end_value", []) or request.GET.getlist(
            "end_value", []
        )

        # Build complete set of valid operator keys from OPERATOR_CHOICES.
        valid_operators = {
            op_key
            for op_list in OPERATOR_CHOICES.values()
            for op_key, _label in op_list
        }

        # Retrieve Meta.exclude for this FilterSet, defaulting to empty list.
        excluded_fields = list(
            getattr(getattr(self, "Meta", None), "exclude", []) or []
        )

        for i, (field, operator) in enumerate(zip(fields, operators)):
            if not field or not operator:
                continue

            # Reject disallowed operators
            if operator not in valid_operators:
                logger.warning(
                    "filter_queryset: rejected invalid operator %r for field %r",
                    operator,
                    field,
                )
                continue

            # Reject excluded fields (including ORM traversals like password__icontains)
            top_level_field = field.split("__")[0]
            if top_level_field in excluded_fields:
                logger.warning(
                    "filter_queryset: rejected excluded field %r (top-level: %r) on %s",
                    field,
                    top_level_field,
                    (
                        queryset.model.__name__
                        if hasattr(queryset, "model")
                        else "unknown"
                    ),
                )
                continue

            try:
                # Get the model from queryset
                model = queryset.model

                if operator == "ne":
                    value = values[i] if i < len(values) else None
                    if value is not None:
                        # Convert boolean value if needed
                        value = self._convert_boolean_value(value, model, field)
                        queryset = queryset.exclude(**{field: value})

                elif operator == "between":
                    start_value = start_values[i] if i < len(start_values) else None
                    end_value = end_values[i] if i < len(end_values) else None

                    if start_value and end_value:
                        queryset = queryset.filter(
                            **{f"{field}__gte": start_value, f"{field}__lte": end_value}
                        )
                    elif start_value:
                        queryset = queryset.filter(**{f"{field}__gte": start_value})
                    elif end_value:
                        queryset = queryset.filter(**{f"{field}__lte": end_value})

                elif operator == "isnull":
                    # For string-like fields, "empty" = NULL or empty string
                    try:
                        field_obj = model._meta.get_field(field)
                        if isinstance(field_obj, STRING_LIKE_FIELDS):
                            queryset = queryset.filter(
                                Q(**{f"{field}__isnull": True})
                                | Q(**{f"{field}__exact": ""})
                            )
                        else:
                            queryset = queryset.filter(**{f"{field}__isnull": True})
                    except (models.FieldDoesNotExist, AttributeError):
                        queryset = queryset.filter(**{f"{field}__isnull": True})

                elif operator == "isnotnull":
                    # For string-like fields, "not empty" = NOT NULL and not empty string
                    try:
                        field_obj = model._meta.get_field(field)
                        if isinstance(field_obj, STRING_LIKE_FIELDS):
                            queryset = queryset.filter(
                                ~Q(**{f"{field}__isnull": True})
                                & ~Q(**{f"{field}__exact": ""})
                            )
                        else:
                            queryset = queryset.filter(**{f"{field}__isnull": False})
                    except (models.FieldDoesNotExist, AttributeError):
                        queryset = queryset.filter(**{f"{field}__isnull": False})

                elif operator in RELATIVE_DATE_OPERATORS:
                    queryset = self._apply_relative_date_filter(
                        queryset, field, operator
                    )

                else:
                    value = values[i] if i < len(values) else None
                    if value is not None:
                        # Convert boolean value if needed
                        value = self._convert_boolean_value(value, model, field)
                        queryset = queryset.filter(**{f"{field}__{operator}": value})

            except Exception as e:
                logger.error("Filter error for %s %s: %s", field, operator, e)

        search_query = self.data.get("search", "") or request.GET.get("search", "")
        if search_query:
            queryset = self.filter_search(queryset, "search", search_query)

        return queryset

    def filter_search(self, queryset, name, value):
        """Handle search across specified fields with smart full name matching"""
        search_fields = getattr(self.Meta, "search_fields", [])
        if not value or not search_fields:
            return queryset

        # Resolve name_split_fields from Meta, or infer from search_fields
        name_split_fields = getattr(self.Meta, "name_split_fields", None)
        if not name_split_fields:
            if "first_name" in search_fields and "last_name" in search_fields:
                name_split_fields = ["first_name", "last_name"]

        stripped = value.strip()
        is_split_search = (
            name_split_fields and len(name_split_fields) == 2 and " " in stripped
        )

        queries = Q()

        if is_split_search:
            parts = stripped.split(None, 1)
            first_part, second_part = parts

            # Only search non-name fields with the full string
            for field in search_fields:
                if field not in name_split_fields:
                    queries |= Q(**{f"{field}__icontains": stripped})

            # Split name search with AND logic
            queries |= Q(
                **{
                    f"{name_split_fields[0]}__icontains": first_part,
                    f"{name_split_fields[1]}__icontains": second_part,
                }
            )
        else:
            # No space — normal search across all fields
            for field in search_fields:
                queries |= Q(**{f"{field}__icontains": value})

        return queryset.filter(queries)
