"""
Offer custom fields in condition field dropdowns, through view / form
extensions.

The condition builders list a model's columns. The views and form below build
their own lists, and expose ``get_extra_field_choices`` (views) or override
``_get_model_field_choices`` (the automation form) for fields that aren't
columns. The extensions here add the model's custom fields.
"""

import logging

from django.apps import apps as django_apps

from horilla.contrib.field_management.hooks.detail import custom_field_selector_items
from horilla.extension.forms import FormExtension
from horilla.extension.view import ViewExtension

logger = logging.getLogger(__name__)


def _custom_field_choices(model):
    """``(value, label)`` pairs for the model's custom fields."""
    try:
        return [(name, label) for label, name in custom_field_selector_items(model)]
    except Exception:
        logger.exception("custom_fields: could not list condition fields")
        return []


class CustomFieldAutomationChoicesExtension(ViewExtension):
    """Custom fields in the automation condition field dropdown."""

    _inherit_view = "horilla.contrib.automations.views.AutomationFieldChoicesView"

    def get_extra_field_choices(self, model):
        return list(super().get_extra_field_choices(model)) + _custom_field_choices(
            model
        )


class CustomFieldModelFieldChoicesExtension(ViewExtension):
    """Custom fields in the generic condition field dropdown."""

    _inherit_view = "horilla.contrib.generics.views.helpers.condition_widget.GetModelFieldChoicesView"

    def get_extra_field_choices(self, model):
        return list(super().get_extra_field_choices(model)) + _custom_field_choices(
            model
        )


class CustomFieldAutomationFormExtension(FormExtension):
    """Custom fields in the automation form's condition field list."""

    _inherit_form = "horilla.contrib.automations.forms.HorillaAutomationForm"

    def _get_model_field_choices(self, model_name):
        choices = list(super()._get_model_field_choices(model_name))
        if not model_name:
            return choices
        for app_config in django_apps.get_app_configs():
            try:
                model = django_apps.get_model(app_config.label, str(model_name).lower())
            except (LookupError, ValueError):
                continue
            return choices + _custom_field_choices(model)
        return choices
