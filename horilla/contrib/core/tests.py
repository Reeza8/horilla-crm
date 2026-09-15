"""Tests for Horilla core RTL assets and web-to-lead field parsing."""

import json
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.template.loader import render_to_string
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from horilla.auth.models import User
from horilla.contrib.core.models import Company
from horilla.urls import reverse
from horilla_crm.leads.models import Lead, LeadCaptureForm, LeadStatus
from horilla_crm.leads.views.web_to_lead import (
    parse_selected_fields,
    render_form_preview,
)


class ParseSelectedFieldsTests(SimpleTestCase):
    """Edit Form must not 500 when selected_fields is empty or invalid JSON."""

    def test_empty_and_invalid_values_become_an_empty_list(self):
        self.assertEqual(parse_selected_fields(""), [])
        self.assertEqual(parse_selected_fields(None), [])
        self.assertEqual(parse_selected_fields("   "), [])
        self.assertEqual(parse_selected_fields("not-json"), [])
        self.assertEqual(parse_selected_fields("{}"), [])

    def test_valid_json_list_is_returned(self):
        self.assertEqual(
            parse_selected_fields('["first_name", "email"]'),
            ["first_name", "email"],
        )


class WebToLeadRtlTemplateTests(SimpleTestCase):
    """Standalone public form follows the same LANGUAGE_BIDI dir pattern as login."""

    def test_public_form_template_uses_language_bidi_dir(self):
        path = (
            Path(settings.BASE_DIR)
            / "horilla_crm"
            / "leads"
            / "templates"
            / "web_to_lead"
            / "public_lead_form.html"
        )
        text = path.read_text(encoding="utf-8")
        self.assertIn('dir="{% if LANGUAGE_BIDI %}rtl{% else %}ltr{% endif %}"', text)
        self.assertIn("inject_html/rtl_assets.html", text)

    def test_form_preview_sets_dir_from_language_bidi(self):
        html = render_to_string(
            "web_to_lead/form_preview.html",
            {"fields": [], "form_name": "Contact Us", "LANGUAGE_BIDI": True},
        )
        self.assertIn('dir="rtl"', html)

    def test_edit_preview_uses_form_language_direction(self):
        html = render_form_preview([], "Contact Us", "", "fa")
        self.assertIn('dir="rtl"', html)
        html = render_form_preview([], "Contact Us", "", "en")
        self.assertIn('dir="ltr"', html)

    def test_edit_form_button_has_persian_translation(self):
        po = (
            Path(settings.BASE_DIR)
            / "horilla_crm"
            / "leads"
            / "locale"
            / "fa"
            / "LC_MESSAGES"
            / "django.po"
        )
        text = po.read_text(encoding="utf-8")
        self.assertIn('msgid "Edit Form"', text)
        self.assertIn('msgstr "ویرایش فرم"', text)


class WebToLeadDuplicateSubmissionTests(TestCase):
    """Repeated clicks on the embedded form must not create duplicate leads."""

    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(
            name="Acme", email="acme@example.com", country="US"
        )
        cls.owner = User.objects.create_user(
            username="owner", email="owner@example.com", password="x"
        )
        LeadStatus.all_objects.create(name="New", probability=0, company=cls.company)
        cls.form_config = LeadCaptureForm.all_objects.create(
            company=cls.company,
            form_name="Contact Us",
            selected_fields=json.dumps(
                ["first_name", "last_name", "email", "lead_company"]
            ),
            header_color="#ed4f38",
            success_message="Thanks",
            success_description="We will contact you.",
            lead_owner=cls.owner,
        )
        cls.url = reverse(
            "leads:public_lead_form", kwargs={"form_id": cls.form_config.id}
        )

    def submit(self, **overrides):
        data = {
            "first_name": "Sara",
            "last_name": "Ahmadi",
            "email": "sara@example.com",
            "lead_company": "Example Ltd",
        }
        data.update(overrides)
        return self.client.post(self.url, data, HTTP_HX_REQUEST="true")

    def test_identical_resubmission_creates_one_lead(self):
        self.assertEqual(self.submit().status_code, 200)
        response = self.submit(email="SARA@example.com")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Thanks")
        self.assertEqual(Lead.all_objects.count(), 1)

    def test_different_data_creates_a_new_lead(self):
        self.submit()
        self.submit(email="other@example.com")
        self.assertEqual(Lead.all_objects.count(), 2)

    def test_old_submission_is_not_treated_as_duplicate(self):
        self.submit()
        Lead.all_objects.update(created_at=timezone.now() - timedelta(hours=1))
        self.submit()
        self.assertEqual(Lead.all_objects.count(), 2)

    @override_settings(WEB_TO_LEAD_DUPLICATE_WINDOW=0)
    def test_check_can_be_disabled(self):
        self.submit()
        self.submit()
        self.assertEqual(Lead.all_objects.count(), 2)

    def test_public_form_drops_clicks_while_a_request_is_in_flight(self):
        self.assertContains(self.client.get(self.url), 'hx-sync="this:drop"')


class WebToLeadRtlCssTests(SimpleTestCase):
    """Form preview and public-form labels are aligned in rtl.css."""

    def test_form_preview_rtl_rules_are_in_rtl_css(self):
        css_path = Path(settings.BASE_DIR) / "static" / "assets" / "css" / "rtl.css"
        css = css_path.read_text(encoding="utf-8")
        self.assertIn('[dir="rtl"] #formPreview label', css)
        self.assertIn('[dir="rtl"] .form-label', css)
