"""Tests for Horilla core RTL assets and web-to-lead field parsing."""

from pathlib import Path

from django.conf import settings
from django.template.loader import render_to_string
from django.test import SimpleTestCase

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
        self.assertIn(
            'dir="{% if LANGUAGE_BIDI %}rtl{% else %}ltr{% endif %}"', text
        )
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


class WebToLeadRtlCssTests(SimpleTestCase):
    """Form preview and public-form labels are aligned in rtl.css."""

    def test_form_preview_rtl_rules_are_in_rtl_css(self):
        css_path = Path(settings.BASE_DIR) / "static" / "assets" / "css" / "rtl.css"
        css = css_path.read_text(encoding="utf-8")
        self.assertIn('[dir="rtl"] #formPreview label', css)
        self.assertIn('[dir="rtl"] .form-label', css)
