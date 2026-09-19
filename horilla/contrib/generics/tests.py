"""
Tests for horilla.contrib.generics.

Unit tests and integration tests for the horilla.contrib.generics app.
"""

from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.test import SimpleTestCase, TestCase
from login_history.models import post_login, post_logout

from horilla.auth.models import User
from horilla.contrib.core.models import Company, ListColumnVisibility
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
