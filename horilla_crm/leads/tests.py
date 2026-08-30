"""
Tests for horilla_crm.leads.

Pins which Lead fields the create/edit modal treats as required, so changes to
the shared requiredness hooks cannot silently alter the lead form.
"""

# Third-party imports (Django)
from django.test import SimpleTestCase

# First party imports (Horilla)
from horilla_crm.leads.forms import LeadFormClass
from horilla_crm.leads.models import Lead


class LeadFormRequirednessTests(SimpleTestCase):
    """Behavior pins for requiredness on the Lead create modal."""

    #: Fields the modal requires today, and the step each one appears on.
    REQUIRED_FIELDS = (
        "first_name",
        "last_name",
        "email",
        "lead_owner",
        "lead_source",
        "lead_status",
        "lead_company",
        "industry",
        "country",
    )

    OPTIONAL_FIELDS = (
        "title",
        "contact_number",
        "fax",
        "no_of_employees",
        "annual_revenue",
        "city",
        "zip_code",
        "requirements",
    )

    def _form(self):
        """Return an unbound stand-in used only to resolve requiredness.

        No admin overrides are configured, so requiredness comes purely from
        the model definition -- which is what these tests pin.
        """
        form = LeadFormClass.__new__(LeadFormClass)
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
                    msg=f"{field_name} should be required on the lead form",
                )

    def test_optional_fields_stay_optional(self):
        """Fields the model allows blank must not become required."""
        form = self._form()
        for field_name in self.OPTIONAL_FIELDS:
            with self.subTest(field=field_name):
                self.assertFalse(
                    form.is_field_required(field_name),
                    msg=f"{field_name} should be optional on the lead form",
                )

    def test_email_requiredness_comes_from_the_model(self):
        """Email is required only because Lead.email declares blank=False."""
        self.assertFalse(Lead._meta.get_field("email").blank)
        self.assertTrue(self._form().is_field_required("email"))

    def test_email_is_mandatory_at_the_database_level(self):
        """Email is both null=False and blank=False, so it has no NULL state."""
        form = self._form()
        self.assertTrue(form.is_field_mandatory("email"))
