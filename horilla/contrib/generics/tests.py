"""
Tests for horilla.contrib.generics.

Unit tests and integration tests for the horilla.contrib.generics app.
"""

# Third-party imports (Django)
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.template.loader import render_to_string
from django.test import RequestFactory, SimpleTestCase, TestCase
from login_history.models import post_login, post_logout

# First party imports (Horilla)
from horilla.auth.models import User
from horilla.contrib.core.models import Company, ListColumnVisibility
from horilla.contrib.generics.templatetags.horilla_tags.history_display import (
    DIFF_VALUE_PREVIEW_LENGTH,
    has_long_diff_value,
    html_to_paragraphs,
    is_long_diff_value,
)
from horilla.contrib.generics.views.helpers.list_column import get_view_columns
from horilla.urls import reverse


class GetViewColumnsVerboseNameTests(SimpleTestCase):
    """get_view_columns() must resolve a string column's real verbose_name.

    Regression test for a mislabeling bug introduced by f759bfa8a: string
    columns were humanized (`col.replace("_", " ").title()`) instead of
    looking up the model field's actual `verbose_name`.
    """

    def test_string_column_uses_the_field_verbose_name(self):
        """`LeadListView.columns` has `lead_status`, whose verbose_name
        ("Lead Stage") deliberately differs from its humanized name
        ("Lead Status").

        `url_name` is passed bare (no namespace prefix) here, matching how
        `HorillaListView` actually populates it for the page's own column
        selector -- see `list_view_url_name` in
        `horilla/contrib/generics/views/list.py`, built from
        `resolver_match.url_name`, not the namespaced `view_name`.
        """
        columns = get_view_columns("leads_list", "leads", "Lead")
        by_field_name = {field_name: label for label, field_name in columns}
        self.assertEqual(by_field_name["lead_status"], "Lead Stage")

    def test_method_based_column_falls_back_to_a_humanized_name(self):
        """`CallProviderListView.columns` has `status_col`, a model method
        with no corresponding `_meta` field, so it can't resolve a
        verbose_name and must keep the humanized fallback."""
        columns = get_view_columns("provider_list", "calls", "CallProvider")
        by_field_name = {field_name: label for label, field_name in columns}
        self.assertEqual(by_field_name["status_col"], "Status Col")


class ColumnSelectorSavesVerboseNameTests(TestCase):
    """The column-selector POST flow must persist the real verbose_name."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # django-login-history reads request.META['HTTP_USER_AGENT'] on
        # login/logout. Django's test client builds a bare HttpRequest, so
        # this KeyErrors unless the signal is disconnected here.
        user_logged_in.disconnect(post_login)
        user_logged_out.disconnect(post_logout)

    @classmethod
    def tearDownClass(cls):
        user_logged_in.connect(post_login)
        user_logged_out.connect(post_logout)
        super().tearDownClass()

    def setUp(self):
        self.company = Company.objects.create(
            name="Acme", email="acme@example.com", country="US"
        )
        self.user = User.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="pass",
            company=self.company,
        )
        self.client.force_login(self.user)

    def test_saved_visible_fields_use_the_real_verbose_name(self):
        """Column selector saves the field's actual verbose name, not the raw label."""
        response = self.client.post(
            reverse("generics:column_selector"),
            data={
                "app_label": "leads",
                "model_name": "Lead",
                "url_name": "leads_list",
                "visible_fields": ["title", "lead_status"],
            },
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200, response.content[:2000])

        visibility = ListColumnVisibility.all_objects.get(
            user=self.user,
            app_label="leads",
            model_name="Lead",
            url_name="leads_list",
        )
        saved = {field_name: label for label, field_name in visibility.visible_fields}
        self.assertEqual(saved["lead_status"], "Lead Stage")


class HistoryDiffValueFullTextTests(SimpleTestCase):
    """Long History diff values render a preview plus their full text, and the
    History tab offers a "Show full text" toggle to switch between them."""

    def render_value(self, value):
        """Render the History diff value partial for a raw diff `value`."""
        return render_to_string(
            "partials/history_diff_value.html", {"value": value}
        ).strip()

    def test_is_long_diff_value_matches_the_preview_length(self):
        """Only values longer than the preview length count as long."""
        self.assertFalse(is_long_diff_value("x" * DIFF_VALUE_PREVIEW_LENGTH))
        self.assertTrue(is_long_diff_value("x" * (DIFF_VALUE_PREVIEW_LENGTH + 1)))

    def test_has_long_diff_value_checks_old_and_new_text(self):
        """A diff counts as long when either side's text would be shortened,
        measured without markup; M2M markers never count."""
        long_text = "x" * (DIFF_VALUE_PREVIEW_LENGTH + 1)
        self.assertTrue(has_long_diff_value(["short", long_text]))
        self.assertTrue(has_long_diff_value([long_text, "short"]))
        self.assertFalse(
            has_long_diff_value(["short", "<p>" + "<b></b>" * 50 + "</p>"])
        )
        self.assertFalse(has_long_diff_value(["__m2m__", "add", "Added", long_text]))
        self.assertFalse(has_long_diff_value(None))

    def test_html_to_paragraphs_keeps_one_line_per_block(self):
        """Paragraphs, list items and line breaks each get their own line."""
        value = (
            "<p>Key requirements:</p><ol><li>Barcode scanning</li>"
            '<li class="x">Daily report</li></ol><p>Line one<br>line two</p>'
        )
        self.assertEqual(
            html_to_paragraphs(value),
            "Key requirements:\n• Barcode scanning\n• Daily report\nLine one\nline two",
        )

    def test_short_value_renders_as_plain_text(self):
        """A short value renders as plain text, with no preview/full wrappers."""
        html = self.render_value("<p>Called the customer</p>")
        self.assertEqual(html, "Called the customer")

    def test_long_value_renders_preview_and_full_paragraphs(self):
        """A long value keeps its tail preview and also carries the full text,
        one line per paragraph."""
        first = "Start of the call summary."
        second = "x" * DIFF_VALUE_PREVIEW_LENGTH
        html = self.render_value(f"<p>{first}</p><p>{second}</p>")
        self.assertIn(
            '<span class="history-value-preview" dir="auto">…'
            + f"{first}, {second}"[-DIFF_VALUE_PREVIEW_LENGTH:]
            + "</span>",
            html,
        )
        self.assertIn(
            f'<span class="history-value-full" dir="auto">{first}\n{second}</span>',
            html,
        )

    def test_long_value_is_escaped_in_both_spans(self):
        """Text that looks like markup is escaped in the preview and full text."""
        value = "x" * DIFF_VALUE_PREVIEW_LENGTH + " if a < b & c"
        html = self.render_value(value)
        self.assertNotIn("a < b", html)
        self.assertEqual(html.count("a &lt; b &amp; c"), 2)

    def test_history_tab_renders_the_full_text_toggle(self):
        """The History tab toolbar has the switch, hidden until JS finds a
        shortened value on the page."""
        request = RequestFactory().get("/history/")
        html = render_to_string(
            "history_tab.html", {"page_obj": None, "request": request}
        )
        self.assertIn('class="history-full-text-toggle', html)
        self.assertIn('role="switch"', html)
        self.assertIn('onclick="toggleHistoryFullText()"', html)
        self.assertIn("Show full text", html)
        self.assertIn('"historyShowFullText"', html)

