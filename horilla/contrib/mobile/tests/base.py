"""
Shared setup for the records and record-page tests: the test model opted in
the way an app opts in (feature + ``MOBILE_MODELS`` settings), a company, an
admin and two normal users with "own records" permissions.
"""

# Third-party imports (Django)
from django.contrib.auth.models import Permission
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.db import connection
from django.test import TestCase
from login_history.models import post_login, post_logout

# First party imports (Horilla)
from horilla.apps import apps
from horilla.auth.models import User
from horilla.contrib.core.models import Company
from horilla.registry.feature import FEATURE_REGISTRY, register_model_for_feature

MOBILE_INSTALLED = apps.is_installed("horilla.contrib.mobile")

if MOBILE_INSTALLED:
    from horilla.contrib.mobile.registry import (
        REGISTRY_KEY,
        register_config,
        unregister_config,
    )

    from .models import MobileTestRecord

# What an app's ``mobile.py`` would declare for the test model.
TEST_MOBILE_SETTINGS = {
    "title_field": "name",
    "phone_fields": ["phone", "mobile_phone"],
    "email_field": "email",
    "status_field": "status",
    "header_fields": ["phone", "city"],
    "row_fields": ["city", "owner"],
    "search_fields": ["city"],
}

PASSWORD = "mobile-pass-123"


class MobileTestBase(TestCase):
    """Opts the test model in, and logs users in without login-history noise."""

    @classmethod
    def setUpClass(cls):
        # Django only syncs test models of apps with a models module, and this
        # app deliberately has none: create the table here, outside the test
        # transaction, and drop it again in tearDownClass.
        with connection.schema_editor() as editor:
            editor.create_model(MobileTestRecord)
        super().setUpClass()
        # django-login-history reads request.META['HTTP_USER_AGENT'] on
        # login/logout, which the test client's bare request doesn't set.
        user_logged_in.disconnect(post_login)
        user_logged_out.disconnect(post_logout)
        register_model_for_feature(model_class=MobileTestRecord, features=["mobile"])
        register_config(MobileTestRecord, TEST_MOBILE_SETTINGS)

    @classmethod
    def tearDownClass(cls):
        unregister_config(MobileTestRecord)
        registered = FEATURE_REGISTRY[REGISTRY_KEY]
        if MobileTestRecord in registered:
            registered.remove(MobileTestRecord)
        user_logged_in.connect(post_login)
        user_logged_out.connect(post_logout)
        super().tearDownClass()
        with connection.schema_editor() as editor:
            editor.delete_model(MobileTestRecord)

    def setUp(self):
        cache.clear()
        self.company = Company.objects.create(
            name="Acme", email="acme@example.com", country="US"
        )
        self.admin = User.objects.create_superuser(
            username="admin-user",
            email="admin@example.com",
            password=PASSWORD,
            company=self.company,
        )
        self.seller = self.make_user("seller")
        self.other_seller = self.make_user("other-seller")
        for user in (self.seller, self.other_seller):
            self.grant(user, MobileTestRecord, "view_own", "change_own")

    def make_user(self, username):
        """A normal user of the test company."""
        return User.objects.create_user(
            username=username,
            email=f"{username}@example.com",
            password=PASSWORD,
            company=self.company,
        )

    def grant(self, user, model, *actions):
        """Give ``user`` ``{action}_{model}`` permissions (created if missing)."""
        content_type = ContentType.objects.get_for_model(model)
        model_name = model._meta.model_name
        for action in actions:
            permission, _created = Permission.objects.get_or_create(
                codename=f"{action}_{model_name}",
                content_type=content_type,
                defaults={"name": f"Can {action} {model_name}"},
            )
            user.user_permissions.add(permission)

    def make_record(self, name, owner=None, **fields):
        """A test record of the test company."""
        return MobileTestRecord.objects.create(
            name=name, owner=owner, company=self.company, **fields
        )
