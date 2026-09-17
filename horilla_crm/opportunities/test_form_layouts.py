"""
Opportunity integration tests for the optional ``horilla.contrib.form_layouts`` app.

Opportunity opts in to form layouts from
``horilla_crm/opportunities/registration.py``. The app's generic behaviour is
tested in the app itself; these tests cover what is specific to Opportunity.
They are skipped when the app is not installed.
"""

# Standard library imports
from importlib import import_module
from unittest import skipUnless

# Third-party imports (Django)
from django.apps import apps as django_apps
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.test import SimpleTestCase, TestCase
from login_history.models import post_login, post_logout

# First party imports (Horilla)
from horilla.apps import apps
from horilla.auth.models import User
from horilla.contrib.core.models import Company, HorillaContentType
from horilla.contrib.utils.middlewares import _thread_local
from horilla.urls import reverse

FORM_LAYOUTS_INSTALLED = django_apps.is_installed("horilla.contrib.form_layouts")
SKIP_REASON = "horilla.contrib.form_layouts is not installed"


def _form_layouts(module):
    """Import a form_layouts module only once the app is known to be installed."""
    return import_module(f"horilla.contrib.form_layouts.{module}")


@skipUnless(FORM_LAYOUTS_INSTALLED, SKIP_REASON)
class OpportunityFormLayoutRegistrationTests(SimpleTestCase):
    """Opportunity's opt-in, next to Opportunity's registration."""

    def test_opportunity_opts_in_to_form_layouts(self):
        """opportunities/registration.py lists the form_layouts feature."""
        opportunity = apps.get_model("opportunities", "Opportunity")

        self.assertTrue(_form_layouts("registry").is_layout_configurable(opportunity))

    def test_opportunity_stage_does_not_opt_in(self):
        """Only Opportunity itself is configurable, not its stage model."""
        stage = apps.get_model("opportunities", "OpportunityStage")

        self.assertFalse(_form_layouts("registry").is_layout_configurable(stage))

    def test_editor_uses_the_opportunity_single_page_form(self):
        """The Opportunity wizard's single-page counterpart provides the fields."""
        # Local imports
        from horilla_crm.opportunities.forms import OpportunitySingleForm

        opportunity = apps.get_model("opportunities", "Opportunity")
        form_class = _form_layouts("utils").get_create_form_class(opportunity)

        self.assertTrue(issubclass(form_class, OpportunitySingleForm))


@skipUnless(FORM_LAYOUTS_INSTALLED, SKIP_REASON)
class OpportunityCreateFormLayoutTests(TestCase):
    """HTTP tests: a saved Opportunity layout trims opportunity creation."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # django-login-history reads request.META['HTTP_USER_AGENT'] on
        # login/logout, which the test client does not send.
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
        self.opportunity = apps.get_model("opportunities", "Opportunity")
        self.opportunity_ct = HorillaContentType.objects.get_for_model(self.opportunity)
        self.layout_field = apps.get_model("form_layouts", "FormLayoutField")
        self.client.force_login(self.user)

    def tearDown(self):
        if hasattr(_thread_local, "request"):
            del _thread_local.request
        super().tearDown()

    def _htmx(self):
        return {"HTTP_HX_REQUEST": "true"}

    def _create(self):
        return self.client.get(
            f"{reverse('opportunities:opportunity_create')}?new=true", **self._htmx()
        )

    def test_create_button_opens_the_wizard_without_a_layout(self):
        """Nothing changes for Opportunity until a layout is saved."""
        self.assertContains(
            self._create(), 'id="opportunity-form-view-multi-container"'
        )

    def test_create_button_opens_the_trimmed_single_form(self):
        """With a layout the opportunity create button renders the trimmed form."""
        self.layout_field.all_objects.create(
            content_type=self.opportunity_ct,
            field_name="next_step",
            sequence=1,
            is_visible=False,
            company=self.company,
        )
        response = self._create()

        self.assertContains(response, 'id="opportunity-form-view-container"')
        self.assertContains(response, 'name="name"')
        self.assertNotContains(response, 'name="next_step"')
        self.assertContains(
            response, reverse("opportunities:opportunity_single_create")
        )

    def test_settings_editor_lists_opportunity_fields(self):
        """The settings editor offers Opportunity with its create form fields."""
        response = self.client.get(
            f"{reverse('form_layouts:form_layout_editor')}?model={self.opportunity_ct.pk}",
            **self._htmx(),
        )

        self.assertContains(response, 'data-field="next_step"')
        self.assertNotContains(response, 'data-field="forecast_category"')
