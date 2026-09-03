"""
Tests for the custom_fields app.
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, RequestFactory

from horilla.contrib.core.models import Company, HorillaContentType
from horilla.contrib.utils.middlewares import _thread_local
from horilla_crm.leads.models import Lead, LeadStatus
from horilla_crm.leads.forms import LeadFormClass, LeadSingleForm
from horilla_crm.opportunities.forms import OpportunityFormClass

from custom_fields.integration import (
    CustomFieldMultiStepMixin,
    CustomFieldSingleFormMixin,
)
from custom_fields.models import CustomFieldDefinition, CustomFieldValue
from custom_fields.utils import (
    build_custom_form_fields,
    load_custom_field_values,
    save_custom_field_values,
)


class CustomFieldDefinitionModelTests(TestCase):
    """Tests for CustomFieldDefinition model."""

    def setUp(self):
        self.company = Company.objects.create(name="Test Co")
        self.ct_lead = HorillaContentType.objects.get(app_label="leads", model="lead")

    def test_create_small_text_field(self):
        defn = CustomFieldDefinition.objects.create(
            content_type=self.ct_lead,
            name="Industry Notes",
            field_type="small_text",
            is_required=False,
            company=self.company,
        )
        self.assertEqual(str(defn), "Industry Notes")
        self.assertTrue(defn.is_active)

    def test_create_choice_field_with_choices(self):
        defn = CustomFieldDefinition.objects.create(
            content_type=self.ct_lead,
            name="Priority",
            field_type="choice",
            choices="Low, Medium, High",
            company=self.company,
        )
        self.assertEqual(defn.get_choices_list(), ["Low", "Medium", "High"])

    def test_unique_together_per_company(self):
        CustomFieldDefinition.objects.create(
            content_type=self.ct_lead,
            name="Field A",
            field_type="small_text",
            company=self.company,
        )
        with self.assertRaises(Exception):
            CustomFieldDefinition.objects.create(
                content_type=self.ct_lead,
                name="Field A",
                field_type="number",
                company=self.company,
            )


class CustomFieldValueModelTests(TestCase):
    """Tests for CustomFieldValue storage and retrieval."""

    def setUp(self):
        self.company = Company.objects.create(name="Test Co")
        self.ct_lead = HorillaContentType.objects.get(app_label="leads", model="lead")
        self.defn_text = CustomFieldDefinition.objects.create(
            content_type=self.ct_lead,
            name="Notes",
            field_type="large_text",
            company=self.company,
        )
        self.defn_number = CustomFieldDefinition.objects.create(
            content_type=self.ct_lead,
            name="Budget",
            field_type="number",
            company=self.company,
        )

    def test_set_and_get_text_value(self):
        cfv = CustomFieldValue(
            field_definition=self.defn_text,
            content_type=self.ct_lead,
            object_id=1,
            company=self.company,
        )
        cfv.set_value("Some long text")
        self.assertEqual(cfv.get_value(), "Some long text")
        self.assertEqual(cfv.value_text, "Some long text")

    def test_set_and_get_number_value(self):
        cfv = CustomFieldValue(
            field_definition=self.defn_number,
            content_type=self.ct_lead,
            object_id=1,
            company=self.company,
        )
        cfv.set_value("1234.56")
        self.assertEqual(cfv.get_value(), Decimal("1234.56"))
        self.assertEqual(cfv.value_number, Decimal("1234.56"))
        self.assertEqual(cfv.value_text, "")


class BuildCustomFormFieldsTests(TestCase):
    """Tests for building Django form fields from definitions."""

    def setUp(self):
        self.company = Company.objects.create(name="Test Co")
        self.ct_lead = HorillaContentType.objects.get(app_label="leads", model="lead")
        self._set_active_company(self.company)

    def _set_active_company(self, company):
        rf = RequestFactory()
        request = rf.get("/")
        request.active_company = company
        _thread_local.request = request

    def test_builds_fields_for_all_types(self):
        CustomFieldDefinition.objects.create(
            content_type=self.ct_lead,
            name="Small",
            field_type="small_text",
            company=self.company,
        )
        CustomFieldDefinition.objects.create(
            content_type=self.ct_lead,
            name="Large",
            field_type="large_text",
            company=self.company,
        )
        CustomFieldDefinition.objects.create(
            content_type=self.ct_lead,
            name="Num",
            field_type="number",
            is_required=True,
            company=self.company,
        )
        CustomFieldDefinition.objects.create(
            content_type=self.ct_lead,
            name="Choice",
            field_type="choice",
            choices="A, B, C",
            company=self.company,
        )

        fields = build_custom_form_fields(Lead)
        self.assertEqual(len(fields), 4)
        for key in fields:
            self.assertTrue(key.startswith("cf_"))

    def test_company_filtering(self):
        """Definitions from other companies should not appear."""
        other_company = Company.objects.create(name="Other Co")
        CustomFieldDefinition.objects.create(
            content_type=self.ct_lead,
            name="My Field",
            field_type="small_text",
            company=self.company,
        )
        CustomFieldDefinition.objects.create(
            content_type=self.ct_lead,
            name="Other Field",
            field_type="small_text",
            company=other_company,
        )
        fields = build_custom_form_fields(Lead)
        labels = [f.label for f in fields.values()]
        self.assertIn("My Field", labels)
        self.assertNotIn("Other Field", labels)


class SaveLoadCustomFieldValuesTests(TestCase):
    """Tests for save/load utility functions."""

    def setUp(self):
        self.company = Company.objects.create(name="Test Co")
        self.ct_lead = HorillaContentType.objects.get(app_label="leads", model="lead")
        self.defn = CustomFieldDefinition.objects.create(
            content_type=self.ct_lead,
            name="Priority",
            field_type="choice",
            choices="Low, High",
            company=self.company,
        )

    def test_save_and_load_roundtrip(self):
        data = {f"cf_{self.defn.pk}": "High"}
        save_custom_field_values(Lead, 42, data, company=self.company)
        loaded = load_custom_field_values(Lead, 42)
        self.assertEqual(loaded[f"cf_{self.defn.pk}"], "High")

    def test_update_existing_value(self):
        data = {f"cf_{self.defn.pk}": "Low"}
        save_custom_field_values(Lead, 42, data, company=self.company)
        data = {f"cf_{self.defn.pk}": "High"}
        save_custom_field_values(Lead, 42, data, company=self.company)
        loaded = load_custom_field_values(Lead, 42)
        self.assertEqual(loaded[f"cf_{self.defn.pk}"], "High")
        self.assertEqual(
            CustomFieldValue.objects.filter(object_id=42).count(), 1
        )


class FormIntegrationTests(TestCase):
    """Tests that custom fields are injected into Lead/Opportunity forms."""

    def setUp(self):
        self.company = Company.objects.create(name="Test Co")
        self.ct_lead = HorillaContentType.objects.get(app_label="leads", model="lead")
        rf = RequestFactory()
        request = rf.get("/")
        request.active_company = self.company
        _thread_local.request = request

        self.defn = CustomFieldDefinition.objects.create(
            content_type=self.ct_lead,
            name="Custom Note",
            field_type="small_text",
            is_required=True,
            company=self.company,
        )

    def test_multi_step_mixin_injected(self):
        self.assertIn(CustomFieldMultiStepMixin, LeadFormClass.__mro__)

    def test_single_form_mixin_injected(self):
        self.assertIn(CustomFieldSingleFormMixin, LeadSingleForm.__mro__)

    def test_custom_fields_visible_on_last_step(self):
        from django import forms as django_forms

        form = LeadFormClass(step=4)
        cf_key = f"cf_{self.defn.pk}"
        self.assertIn(cf_key, form.fields)
        self.assertFalse(
            isinstance(form.fields[cf_key].widget, django_forms.HiddenInput)
        )
        self.assertTrue(form.fields[cf_key].required)

    def test_custom_fields_hidden_on_other_steps(self):
        from django import forms as django_forms

        form = LeadFormClass(step=1)
        cf_key = f"cf_{self.defn.pk}"
        self.assertIn(cf_key, form.fields)
        self.assertTrue(
            isinstance(form.fields[cf_key].widget, django_forms.HiddenInput)
        )

    def test_custom_fields_in_single_form(self):
        form = LeadSingleForm()
        cf_key = f"cf_{self.defn.pk}"
        self.assertIn(cf_key, form.fields)
        self.assertEqual(form.fields[cf_key].label, "Custom Note")

    def test_opportunity_form_integration(self):
        ct_opp = HorillaContentType.objects.get(
            app_label="opportunities", model="opportunity"
        )
        CustomFieldDefinition.objects.create(
            content_type=ct_opp,
            name="Deal Size",
            field_type="number",
            company=self.company,
        )
        form = OpportunityFormClass(step=3)
        cf_keys = [k for k in form.fields if k.startswith("cf_")]
        self.assertEqual(len(cf_keys), 1)

    def test_html_required_attribute_is_disabled(self):
        """Last-step Save must not be blocked by native browser validation."""
        form = LeadFormClass(step=4)
        self.assertFalse(form.use_required_attribute)
        cf_key = f"cf_{self.defn.pk}"
        html = str(form[cf_key])
        self.assertNotIn("required", html)

    def test_save_m2m_persists_custom_fields(self):
        from horilla.auth.models import User
        from horilla_crm.leads.models import LeadStatus

        owner = User.objects.create_user(
            username="owner", email="owner@test.com", password="x"
        )
        owner.company = self.company
        owner.save()
        status = LeadStatus.objects.create(
            name="New", order=1, probability=10, company=self.company
        )
        cf_key = f"cf_{self.defn.pk}"
        data = {
            "title": "Acme Lead",
            "first_name": "Ada",
            "last_name": "Lovelace",
            "email": "ada@example.com",
            "lead_owner": owner.pk,
            "lead_source": "website",
            "lead_status": status.pk,
            "lead_company": "Acme",
            "industry": "finance",
            "country": "US",
            "requirements": "Need a demo",
            cf_key: "Must follow up Friday",
        }
        form = LeadFormClass(data=data, step=4, form_data=data)
        self.assertTrue(form.is_valid(), form.errors)
        instance = form.save(commit=False)
        instance.company = self.company
        instance.save()
        form.save_m2m()
        loaded = load_custom_field_values(Lead, instance.pk)
        self.assertEqual(loaded[cf_key], "Must follow up Friday")


class CustomFieldListActionTests(TestCase):
    """List-view action attrs must survive str.format() placeholder replacement."""

    def setUp(self):
        self.company = Company.objects.create(name="Test Co")
        self.ct_lead = HorillaContentType.objects.get(app_label="leads", model="lead")
        rf = RequestFactory()
        request = rf.get("/")
        request.active_company = self.company
        _thread_local.request = request
        self.defn = CustomFieldDefinition.objects.create(
            content_type=self.ct_lead,
            name="Follow-up Date",
            field_type="small_text",
            company=self.company,
        )

    def test_delete_action_attrs_format_without_keyerror(self):
        from horilla.contrib.generics.templatetags.horilla_tags.field_filters import (
            render_action_button,
        )

        from custom_fields.views import CustomFieldListView

        delete_action = CustomFieldListView.actions[1]
        html = render_action_button(delete_action, self.defn)
        self.assertIn("check_dependencies", html)
        self.assertIn(str(self.defn.get_delete_url()), html)


class CustomFieldDetailViewTests(TestCase):
    """Custom fields must appear on Lead/Opportunity detail pages."""

    def setUp(self):
        self.company = Company.objects.create(name="Test Co")
        self.ct_lead = HorillaContentType.objects.get(app_label="leads", model="lead")
        rf = RequestFactory()
        request = rf.get("/")
        request.active_company = self.company
        _thread_local.request = request
        self.defn = CustomFieldDefinition.objects.create(
            content_type=self.ct_lead,
            name="Follow-up Date",
            field_type="small_text",
            company=self.company,
        )

    def test_detail_context_includes_custom_fields(self):
        from custom_fields.integration import apply_custom_fields_to_detail_context
        from horilla_crm.leads.models import Lead

        lead = Lead(pk=77)
        save_custom_field_values(
            Lead,
            77,
            {f"cf_{self.defn.pk}": "September 10"},
            company=self.company,
        )
        context = {"body": [("First Name", "first_name")]}
        apply_custom_fields_to_detail_context(context, lead)
        self.assertIn(("Follow-up Date", f"cf_{self.defn.pk}"), context["body"])
        self.assertEqual(getattr(lead, f"cf_{self.defn.pk}"), "September 10")
        self.assertIn(f"cf_{self.defn.pk}", context["non_editable_fields"])

    def test_detail_mixins_injected(self):
        from custom_fields.integration import CustomFieldDetailMixin
        from horilla_crm.leads.views.core import LeadDetailView
        from horilla_crm.leads.views.detail_tabs import LeadsDetailTab
        from horilla_crm.opportunities.views.core.detail import (
            OpportunityDetailTab,
            OpportunityDetailView,
        )

        self.assertIn(CustomFieldDetailMixin, LeadDetailView.__mro__)
        self.assertIn(CustomFieldDetailMixin, LeadsDetailTab.__mro__)
        self.assertIn(CustomFieldDetailMixin, OpportunityDetailView.__mro__)
        self.assertIn(CustomFieldDetailMixin, OpportunityDetailTab.__mro__)
