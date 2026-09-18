"""Tests for Opportunity field requirements."""

from unittest import skipUnless

from django.test import TestCase

from horilla.apps import apps
from horilla.auth.models import User
from horilla.contrib.core.models import Company, HorillaContentType
from horilla.contrib.utils.middlewares import _thread_local
from horilla.extension.forms import resolve_form_class
from horilla.extension.forms.bootstrap import apply_form_extensions
from horilla.extension.forms.registry import FORM_EXTENSION_REGISTRY

_FIELD_REQUIREMENTS_INSTALLED = apps.is_installed("horilla.contrib.field_requirements")

if _FIELD_REQUIREMENTS_INSTALLED:
    from horilla.contrib.field_requirements.extensions import (
        iter_configurable_model_forms,
        register_discovered_form_extensions,
    )
    from horilla.contrib.field_requirements.models import FieldRequirement


def _activate_company(company):
    """Point CompanyFilteredManager at ``company`` for the current thread."""
    from types import SimpleNamespace

    _thread_local.request = SimpleNamespace(
        active_company=company,
        session={},
        user=None,
    )


@skipUnless(
    _FIELD_REQUIREMENTS_INSTALLED, "horilla.contrib.field_requirements not installed"
)
class OpportunityFieldRequirementFormExtensionTests(TestCase):
    """Tests that stored overrides actually change Opportunity forms."""

    def setUp(self):
        self.company = Company.objects.create(
            name="Acme",
            email="acme@example.com",
            country="US",
        )
        self.user = User.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="pass",
            company=self.company,
        )
        self.opportunity = apps.get_model("opportunities", "Opportunity")
        self.opportunity_ct = HorillaContentType.objects.get_for_model(self.opportunity)
        _activate_company(self.company)
        register_discovered_form_extensions()
        apply_form_extensions(force=True)

    def tearDown(self):
        if hasattr(_thread_local, "request"):
            del _thread_local.request
        super().tearDown()

    def _override(self, field_name, is_required):
        return FieldRequirement.objects.create(
            content_type=self.opportunity_ct,
            field_name=field_name,
            is_required=is_required,
            company=self.company,
        )

    def test_required_description_override_on_opportunity_form(self):
        """A blank=True field can be made required without touching the model."""
        self._override("description", True)
        from horilla_crm.opportunities.forms import OpportunitySingleForm

        form = resolve_form_class(OpportunitySingleForm)()
        self.assertTrue(form.fields["description"].required)

    def test_opportunity_email_override_does_not_appear_on_create_form(self):
        """Opportunity create/edit forms exclude email, so the override is a no-op there."""
        self._override("email", False)
        from horilla_crm.opportunities.forms import OpportunitySingleForm

        form = resolve_form_class(OpportunitySingleForm)()
        self.assertNotIn("email", form.fields)


@skipUnless(
    _FIELD_REQUIREMENTS_INSTALLED, "horilla.contrib.field_requirements not installed"
)
class OpportunityFormExtensionDiscoveryTests(TestCase):
    """Discovery registers Opportunity's own forms."""

    def setUp(self):
        register_discovered_form_extensions()
        apply_form_extensions(force=True)

    def test_discovery_registers_opportunity_forms(self):
        """Opportunity create-edit forms are extended; Account is not."""
        discovered = {
            f"{form.__module__}.{form.__name__}"
            for form in iter_configurable_model_forms()
        }
        self.assertIn(
            "horilla_crm.opportunities.forms.OpportunitySingleForm", discovered
        )
        self.assertIn(
            "horilla_crm.opportunities.forms.OpportunityFormClass", discovered
        )
        self.assertNotIn("horilla_crm.accounts.forms.AccountFormClass", discovered)

        self.assertNotIn(
            "horilla_crm.accounts.forms.AccountFormClass", FORM_EXTENSION_REGISTRY
        )
