"""
Contribute custom fields to condition builders and rule engines (e.g. Lead
assignment rules) through the generic condition-field extension hook
(``register_condition_field_extension``), instead of generics/core or a
consumer app (e.g. leads) importing custom_fields by name.

See horilla/horilla-crm#45.
"""

# Standard library imports
import logging

from custom_fields.models import CustomFieldDefinition, CustomFieldValue
from custom_fields.utils import (
    get_custom_field_definitions,
    is_custom_field_name,
    parse_custom_field_pk,
    safe_custom_field_label,
)

# First party imports (Horilla)
from horilla.contrib.core.models import HorillaContentType
from horilla.contrib.generics.forms.condition_fields import (
    register_condition_field_extension,
)

logger = logging.getLogger(__name__)


# Maps custom_fields' own CustomFieldDefinition.FIELD_TYPES to the small,
# custom_fields-agnostic vocabulary condition_widget.py renders widgets from,
# and to a key into horilla.contrib.generics.filters.OPERATOR_CHOICES.
_WIDGET_BY_FIELD_TYPE = {
    "small_text": "text",
    "large_text": "textarea",
    "number": "number",
    "single_choice": "select",
    "choice": "multiselect",
}
_OPERATOR_TYPE_BY_FIELD_TYPE = {
    "small_text": "text",
    "large_text": "other",
    "number": "number",
    "single_choice": "choice",
    "choice": "choice",
}


class CustomFieldConditionExtension:
    """Exposes user-defined 'cf_<id>' custom fields as condition-builder fields."""

    def owns(self, field_name):
        """Return True when ``field_name`` is a ``cf_*`` custom-field key."""
        return is_custom_field_name(field_name)

    def _get_definition(self, field_name):
        """Load the ``CustomFieldDefinition`` for a ``cf_<id>`` field name."""
        pk = parse_custom_field_pk(field_name)
        if pk is None:
            return None
        return CustomFieldDefinition.objects.filter(pk=pk).first()

    def get_choices(self, model):
        """Return ``(cf_<id>, label)`` pairs for the model's custom fields."""
        return [
            (f"cf_{definition.pk}", safe_custom_field_label(definition))
            for definition in get_custom_field_definitions(model)
        ]

    def get_label(self, field_name):
        """Return the display label for a ``cf_*`` field, or None if missing."""
        definition = self._get_definition(field_name)
        return safe_custom_field_label(definition) if definition else None

    def get_widget_info(self, field_name):
        """Return widget/operator metadata for the condition-value HTMX UI."""
        definition = self._get_definition(field_name)
        if not definition:
            return None
        info = {
            "widget": _WIDGET_BY_FIELD_TYPE.get(definition.field_type, "text"),
            "operator_type": _OPERATOR_TYPE_BY_FIELD_TYPE.get(
                definition.field_type, "text"
            ),
        }
        if definition.field_type in ("single_choice", "choice"):
            info["choices"] = [(c, c) for c in definition.get_choices_list()]
        return info

    def get_value(self, field_name, instance):
        """Return the stored custom-field value for rule-engine evaluation."""
        definition = self._get_definition(field_name)
        if not definition:
            logger.warning(
                "Condition field extension: custom field '%s' no longer exists",
                field_name,
            )
            return None
        content_type = HorillaContentType.objects.get_for_model(instance)
        cfv = CustomFieldValue.objects.filter(
            field_definition=definition,
            content_type=content_type,
            object_id=instance.pk,
        ).first()
        if not cfv:
            return ""
        value = cfv.get_value()
        if isinstance(value, list):
            return ",".join(str(item) for item in value)
        return "" if value is None else str(value)


register_condition_field_extension(CustomFieldConditionExtension())
