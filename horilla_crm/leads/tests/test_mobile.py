"""
Leads in the optional phone mode (``horilla.contrib.mobile``), with the
settings in ``leads/mobile.py``. Skipped when the mobile app isn't installed.
"""

# Standard library imports
from unittest import skipUnless

# Third-party imports (Django)
from django.contrib.auth.models import Permission
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from login_history.models import post_login, post_logout

# First party imports (Horilla)
from horilla.apps import apps
from horilla.auth.models import User
from horilla.contrib.core.models import Company
from horilla_crm.leads.models import Lead, LeadStatus

MOBILE_INSTALLED = apps.is_installed("horilla.contrib.mobile")


@skipUnless(MOBILE_INSTALLED, "horilla.contrib.mobile is not installed")
class LeadOnThePhoneTests(TestCase):
    """A lead owner finds, opens and calls their lead on the phone."""

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
        self.seller = User.objects.create_user(
            username="seller",
            email="seller@example.com",
            password="pass",
            company=self.company,
        )
        permission, _created = Permission.objects.get_or_create(
            codename="view_own_lead",
            content_type=ContentType.objects.get_for_model(Lead),
            defaults={"name": "Can view own lead"},
        )
        self.seller.user_permissions.add(permission)
        status = LeadStatus.objects.create(
            name="New", probability=10, company=self.company
        )
        self.lead = Lead.objects.create(
            title="Annual support contract",
            first_name="Ada",
            last_name="Lovelace",
            email="ada@example.com",
            contact_number="0912 345 6789",
            lead_company="Prospect Pioneers",
            lead_source="website",
            industry="technology",
            lead_owner=self.seller,
            lead_status=status,
            company=self.company,
        )
        self.client.force_login(self.seller)

    def test_the_list_shows_the_title_the_name_and_a_call_button(self):
        response = self.client.get("/m/records/", {"model": "leads.lead"})
        self.assertContains(response, "Annual support contract")
        self.assertContains(response, "<bdi>Ada Lovelace</bdi>")
        self.assertContains(response, 'href="tel:09123456789"')

    def test_search_finds_a_lead_by_name_or_company(self):
        for query in ("Lovelace", "Pioneers"):
            response = self.client.get("/m/records/", {"q": query})
            self.assertContains(
                response, f"/m/records/leads/lead/{self.lead.pk}/", msg_prefix=query
            )

    def test_the_lead_page_has_call_email_and_the_stage(self):
        response = self.client.get(f"/m/records/leads/lead/{self.lead.pk}/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'href="tel:09123456789"')
        self.assertContains(response, 'href="mailto:ada@example.com"')
        self.assertEqual(response.context["status"]["field"], "lead_status")
