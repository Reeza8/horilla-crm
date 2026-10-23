"""
Accounts in the optional phone mode (``horilla.contrib.mobile``), with the
settings in ``accounts/mobile.py``. Skipped when the mobile app isn't
installed.
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
from horilla_crm.accounts.models import Account

MOBILE_INSTALLED = apps.is_installed("horilla.contrib.mobile")


@skipUnless(MOBILE_INSTALLED, "horilla.contrib.mobile is not installed")
class AccountOnThePhoneTests(TestCase):
    """An account owner finds, opens and calls their account on the phone."""

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
            codename="view_own_account",
            content_type=ContentType.objects.get_for_model(Account),
            defaults={"name": "Can view own account"},
        )
        self.seller.user_permissions.add(permission)
        self.account = Account.objects.create(
            name="Aria Trading",
            industry="technology",
            billing_city="Tehran",
            contact_number="021 8800 1122",
            account_owner=self.seller,
            company=self.company,
        )
        self.client.force_login(self.seller)

    def test_the_list_shows_the_city_and_a_call_button(self):
        response = self.client.get("/m/records/", {"model": "accounts.account"})
        self.assertContains(response, "Aria Trading")
        self.assertContains(response, "<bdi>Tehran</bdi>")
        self.assertContains(response, 'href="tel:02188001122"')

    def test_the_account_page_opens(self):
        response = self.client.get(f"/m/records/accounts/account/{self.account.pk}/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'href="tel:02188001122"')
