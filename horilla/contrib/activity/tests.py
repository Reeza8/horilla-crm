"""
Tests for the activity app
"""

# Third-party imports (Django)
from django.contrib.auth.models import Permission
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.test import TestCase
from login_history.models import post_login, post_logout

# First party imports (Horilla)
from horilla.auth.models import User
from horilla.contrib.core.models import Company, HorillaContentType
from horilla.urls import reverse

# Local imports
from horilla_crm.leads.models import Lead, LeadStatus

from .models import Activity


class ActivityRelatedToTabTests(TestCase):
    """The Related To tab shows the activity's related record inside the activity."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # django-login-history reads request.META['HTTP_USER_AGENT'] on
        # login/logout, which the test client's bare request doesn't set.
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
        self.admin = User.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="pass",
            company=self.company,
        )
        status = LeadStatus.objects.create(
            name="New", probability=10, company=self.company
        )
        self.lead = Lead.objects.create(
            first_name="Ada",
            last_name="Lovelace",
            email="ada@example.com",
            lead_company="Prospect Pioneers",
            lead_source="website",
            industry="technology",
            lead_owner=self.admin,
            lead_status=status,
            company=self.company,
        )
        self.activity = Activity.objects.create(
            subject="Send the proposal",
            activity_type="task",
            status="not_started",
            owner=self.admin,
            content_type=HorillaContentType.objects.get_for_model(Lead),
            object_id=self.lead.pk,
            company=self.company,
        )
        self.tab_url = reverse(
            "activity:activity_related_to_tab", kwargs={"pk": self.activity.pk}
        )
        self.lead_url = str(self.lead.get_detail_url())

    def _make_user(self, username, *perms):
        """Create a non-superuser in the same company with ``app_label.codename`` perms."""
        user = User.objects.create_user(
            username=username,
            email=f"{username}@example.com",
            password="pass",
            company=self.company,
        )
        for perm in perms:
            app_label, codename = perm.split(".")
            user.user_permissions.add(
                Permission.objects.get(
                    content_type__app_label=app_label, codename=codename
                )
            )
        return user

    def _get_tab(self, user, **headers):
        self.client.force_login(user)
        return self.client.get(self.tab_url, HTTP_HX_REQUEST="true", **headers)

    def test_tab_is_listed_right_after_details(self):
        """The activity detail tab bar has Related To between Details and Notes."""
        self.client.force_login(self.admin)
        response = self.client.get(
            reverse("activity:activity_detail_view_tabs"),
            {"object_id": self.activity.pk},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn(self.tab_url, html)
        self.assertLess(
            html.index('id="tab-details"'), html.index('id="tab-related-to"')
        )
        self.assertLess(
            html.index('id="tab-related-to"'), html.index('id="tab-notes-attachments"')
        )

    def _tab_bar(self, user):
        self.client.force_login(user)
        response = self.client.get(
            reverse("activity:activity_detail_view_tabs"),
            {"object_id": self.activity.pk},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        return response.content.decode()

    def test_tab_is_hidden_without_access_to_the_related_record(self):
        """A user who can see the activity but not the lead gets no Related To tab."""
        user = self._make_user("outsider", "activity.view_activity")
        self.assertNotIn('id="tab-related-to"', self._tab_bar(user))

    def test_tab_is_hidden_when_there_is_no_related_record(self):
        """An activity that isn't related to any record gets no Related To tab."""
        self.activity.content_type = None
        self.activity.object_id = None
        self.activity.save()
        self.assertNotIn('id="tab-related-to"', self._tab_bar(self.admin))

    def test_shows_related_record_fields_link_and_edit_button(self):
        """A user who can change the lead sees its fields, the link and Edit Details."""
        response = self._get_tab(self.admin)
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('id="activity-related-to-tab"', html)
        self.assertIn(str(self.lead), html)
        self.assertIn(f'hx-get="{self.lead_url}?section=sales"', html)
        self.assertIn("ada@example.com", html)
        self.assertIn("Edit Details", html)
        # The edit form is loaded for the lead, not the activity.
        self.assertIn(
            reverse(
                "generics:edit_all_fields",
                kwargs={"pk": self.lead.pk, "app_label": "leads", "model_name": "lead"},
            ),
            html,
        )
        self.assertIn('hx-target="closest #details-tab-content"', html)

    def test_view_only_user_gets_no_edit_button(self):
        """Edit Details stays hidden for a user who can only view the lead."""
        user = self._make_user("viewer", "activity.view_activity", "leads.view_lead")
        response = self._get_tab(user)
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn("ada@example.com", html)
        self.assertIn(f'hx-get="{self.lead_url}?section=sales"', html)
        self.assertNotIn("Edit Details", html)

    def test_user_without_lead_access_sees_no_fields_or_link(self):
        """The lead's own access rules still apply inside the activity."""
        user = self._make_user("outsider", "activity.view_activity")
        response = self._get_tab(user)
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn(str(self.lead), html)
        self.assertNotIn(self.lead_url, html)
        self.assertNotIn("ada@example.com", html)
        self.assertIn("You do not have permission to view this.", html)

    def test_record_outside_the_active_company_is_not_shown(self):
        """A related record in another company 404s on its own page; don't link it."""
        other_company = Company.objects.create(
            name="Other", email="other@example.com", country="US"
        )
        Lead.all_objects.filter(pk=self.lead.pk).update(company=other_company)
        response = self._get_tab(self.admin)
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertNotIn(self.lead_url, html)
        self.assertNotIn("ada@example.com", html)
        self.assertIn("You do not have permission to view this.", html)

    def test_activity_without_related_record_shows_empty_state(self):
        """No related record renders an empty state, not an error."""
        self.activity.content_type = None
        self.activity.object_id = None
        self.activity.save()
        response = self._get_tab(self.admin)
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "This activity is not related to any record.", response.content.decode()
        )

    def test_cancel_edit_reloads_only_the_details_grid(self):
        """Cancel on Edit Details targets #details-tab-content; no second header."""
        response = self._get_tab(self.admin, HTTP_HX_TARGET="details-tab-content")
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('id="details-tab-content"', html)
        self.assertIn("ada@example.com", html)
        self.assertNotIn('id="activity-related-to-tab"', html)
