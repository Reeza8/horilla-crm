"""
Tests for horilla_crm.opportunities.

Pins which Opportunity fields the create/edit modal treats as required, so
changes to the shared requiredness hooks cannot silently alter the form.
"""

# Third-party imports (Django)
from django.test import SimpleTestCase

# First party imports (Horilla)
from horilla_crm.opportunities.forms import OpportunityFormClass


class OpportunityFormRequirednessTests(SimpleTestCase):
    """Behavior pins for requiredness on the Opportunity create modal."""

    REQUIRED_FIELDS = ("name", "stage", "owner")

    OPTIONAL_FIELDS = (
        "amount",
        "quantity",
        "close_date",
        "account",
        "lead_source",
        "opportunity_type",
        "primary_campaign_source",
        "next_step",
        "order_number",
        "delivery_installation_status",
        "tracking_number",
        "main_competitors",
        "description",
    )

    def _form(self):
        """Return an unbound stand-in used only to resolve requiredness.

        No admin overrides are configured, so requiredness comes purely from
        the model definition -- which is what these tests pin.
        """
        form = OpportunityFormClass.__new__(OpportunityFormClass)
        form.fields = {}
        form.instance = None
        form.field_requirement_overrides = {}
        return form

    def test_required_fields_stay_required(self):
        """Model-derived requiredness still marks these fields mandatory."""
        form = self._form()
        for field_name in self.REQUIRED_FIELDS:
            with self.subTest(field=field_name):
                self.assertTrue(
                    form.is_field_required(field_name),
                    msg=f"{field_name} should be required on the opportunity form",
                )

    def test_optional_fields_stay_optional(self):
        """Fields the model allows blank must not become required."""
        form = self._form()
        for field_name in self.OPTIONAL_FIELDS:
            with self.subTest(field=field_name):
                self.assertFalse(
                    form.is_field_required(field_name),
                    msg=f"{field_name} should be optional on the opportunity form",
                )

    def test_probability_is_never_required(self):
        """Probability is auto-derived from the stage, so it must stay optional.

        The model already declares it ``blank=True``, and
        ``_make_probability_readonly`` additionally forces ``required = False`` in
        ``__init__``. Pin the model side so the field cannot become mandatory
        through the requiredness hook.
        """
        self.assertFalse(self._form().is_field_required("probability"))

    def test_required_fields_are_mandatory_at_the_database_level(self):
        """The three required fields have no NULL state to fall back on."""
        form = self._form()
        for field_name in self.REQUIRED_FIELDS:
            with self.subTest(field=field_name):
                self.assertTrue(form.is_field_mandatory(field_name))
