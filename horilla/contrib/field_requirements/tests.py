"""
Tests for the field requirements app.

Covers feature-registry opt-in and the safety rules that decide whether a
field may be made optional without breaking inserts.
"""

# Standard library imports
import importlib
from types import SimpleNamespace

# Third-party imports (Django)
from django.test import SimpleTestCase, TestCase

# First party imports (Horilla)
from horilla.apps import apps
from horilla.contrib.core.models import Company, HorillaContentType
from horilla.contrib.field_requirements.models import FieldRequirement
from horilla.contrib.field_requirements.registry import (
    REGISTRY_KEY,
    can_relax_requirement,
    get_configurable_fields,
    get_configurable_models,
    get_excluded_fields,
    get_relax_blocked_reason,
    is_requirement_configurable,
)
from horilla.contrib.field_requirements.utils import get_field_requirements_for_model
from horilla.contrib.utils.middlewares import _thread_local
from horilla.core.exceptions import ValidationError
from horilla.db import models
from horilla.registry.feature import FEATURE_CONFIG, FEATURE_REGISTRY


class FeatureRegistrationTests(SimpleTestCase):
    """Tests that field requirements is a selective feature, not a decorator."""

    def test_feature_is_registered(self):
        """The contrib app registers the feature against the shared registry."""
        self.assertEqual(FEATURE_CONFIG.get("field_requirements"), REGISTRY_KEY)

    def test_lead_and_opportunity_opt_in(self):
        """Lead and Opportunity are the models that opted in."""
        lead = apps.get_model("leads", "Lead")
        opportunity = apps.get_model("opportunities", "Opportunity")
        registered = FEATURE_REGISTRY.get(REGISTRY_KEY, [])

        self.assertIn(lead, registered)
        self.assertIn(opportunity, registered)
        self.assertTrue(is_requirement_configurable(lead))
        self.assertTrue(is_requirement_configurable(opportunity))

    def test_all_true_models_do_not_opt_in_automatically(self):
        """Account and User use all=True but must not become configurable."""
        account = apps.get_model("accounts", "Account")
        user = apps.get_model("core", "HorillaUser")
        registered = FEATURE_REGISTRY.get(REGISTRY_KEY, [])

        self.assertNotIn(account, registered)
        self.assertNotIn(user, registered)
        self.assertFalse(is_requirement_configurable(account))
        self.assertFalse(is_requirement_configurable(user))

    def test_configurable_models_lists_opted_in_models(self):
        """get_configurable_models returns the registry contents."""
        lead = apps.get_model("leads", "Lead")
        opportunity = apps.get_model("opportunities", "Opportunity")
        account = apps.get_model("accounts", "Account")
        configured = get_configurable_models()

        self.assertIn(lead, configured)
        self.assertIn(opportunity, configured)
        self.assertNotIn(account, configured)

    def test_legacy_decorator_registry_does_not_exist(self):
        """Opt-in no longer lives in a dedicated registry module."""
        with self.assertRaises(ModuleNotFoundError):
            importlib.import_module("horilla.registry.field_requirement_registry")

    def test_crm_model_modules_do_not_import_this_app(self):
        """Lead and Opportunity model files stay free of this feature."""
        lead = apps.get_model("leads", "Lead")
        opportunity = apps.get_model("opportunities", "Opportunity")
        self.assertNotIn("field_requirement", lead.__module__)
        self.assertNotIn("field_requirement", opportunity.__module__)


class CanRelaxRequirementTests(SimpleTestCase):
    """Tests for the rule deciding whether a field may be made optional."""

    def test_nullable_field_can_be_relaxed(self):
        """A NULL-able column has somewhere to put an absent value."""
        self.assertTrue(can_relax_requirement(models.DateField(null=True)))

    def test_text_like_field_can_be_relaxed(self):
        """Text columns store the empty string, so they never need NULL."""
        for field in (
            models.CharField(),
            models.EmailField(),
            models.TextField(),
            models.URLField(),
            models.SlugField(),
        ):
            with self.subTest(field=type(field).__name__):
                self.assertTrue(can_relax_requirement(field))

    def test_field_with_default_can_be_relaxed(self):
        """A default supplies the value the user did not enter."""
        self.assertTrue(can_relax_requirement(models.IntegerField(default=0)))

    def test_numeric_and_date_fields_cannot_be_relaxed(self):
        """These columns reject both NULL and the empty string."""
        for field in (
            models.IntegerField(),
            models.DecimalField(),
            models.DateField(),
            models.DateTimeField(),
            models.BooleanField(),
        ):
            with self.subTest(field=type(field).__name__):
                self.assertFalse(can_relax_requirement(field))

    def test_missing_field_cannot_be_relaxed(self):
        """A field that no longer resolves is never treated as relaxable."""
        self.assertFalse(can_relax_requirement(None))

    def test_blocked_reason_is_only_given_when_blocked(self):
        """The explanation accompanies a refusal and nothing else."""
        self.assertIsNone(get_relax_blocked_reason(models.CharField()))
        self.assertIn(
            "empty value",
            str(get_relax_blocked_reason(models.IntegerField())),
        )

    def test_lead_email_can_be_relaxed(self):
        """Lead.email is a text-like column, so making it optional is safe."""
        lead = apps.get_model("leads", "Lead")
        self.assertTrue(can_relax_requirement(lead._meta.get_field("email")))

    def test_lead_status_cannot_be_relaxed(self):
        """Lead Stage is a non-nullable FK with nowhere to store an empty value."""
        lead = apps.get_model("leads", "Lead")
        self.assertFalse(can_relax_requirement(lead._meta.get_field("lead_status")))


class ConfigurableFieldsTests(SimpleTestCase):
    """Tests for which fields appear as configurable on an opted-in model."""

    def test_unregistered_model_has_no_configurable_fields(self):
        """Models that did not opt in expose no fields."""
        account = apps.get_model("accounts", "Account")
        self.assertEqual(get_configurable_fields(account), [])

    def test_object_without_meta_is_not_configurable(self):
        """Guards the registry against being handed a non-model."""
        self.assertFalse(is_requirement_configurable(object()))

    def test_bookkeeping_fields_are_excluded(self):
        """Audit columns and the primary key must never be configurable."""

        class _WithExcludes:
            """Stand-in model carrying the usual exclude list."""

            field_permissions_exclude = ["company", "created_at"]
            requirement_config_exclude = ["lead_score"]

        excluded = get_excluded_fields(_WithExcludes)

        self.assertIn("id", excluded)
        self.assertIn("pk", excluded)
        self.assertIn("company", excluded)
        self.assertIn("created_at", excluded)
        self.assertIn("lead_score", excluded)

    def test_lead_user_fields_are_configurable_and_audit_fields_are_not(self):
        """Lead email is offered; company, pk, and audit columns are not."""
        lead = apps.get_model("leads", "Lead")
        names = {field.name for field in get_configurable_fields(lead)}

        self.assertIn("email", names)
        self.assertIn("first_name", names)
        self.assertIn("lead_status", names)
        self.assertNotIn("id", names)
        self.assertNotIn("company", names)
        self.assertNotIn("created_at", names)
        self.assertNotIn("is_active", names)


def _activate_company(company):
    """Point CompanyFilteredManager at ``company`` for the current thread."""
    _thread_local.request = SimpleNamespace(
        active_company=company,
        session={},
        user=None,
    )


class FieldRequirementModelTests(TestCase):
    """Tests for FieldRequirement.clean and unique_together."""

    def setUp(self):
        self.company = Company.objects.create(
            name="Acme",
            email="acme@example.com",
            country="US",
        )
        self.lead = apps.get_model("leads", "Lead")
        self.lead_ct = HorillaContentType.objects.get_for_model(self.lead)
        _activate_company(self.company)

    def tearDown(self):
        if hasattr(_thread_local, "request"):
            del _thread_local.request
        super().tearDown()

    def _requirement(self, **kwargs):
        defaults = {
            "content_type": self.lead_ct,
            "field_name": "email",
            "is_required": False,
            "company": self.company,
        }
        defaults.update(kwargs)
        return FieldRequirement(**defaults)

    def _clean(self, row):
        """Run model validation without Horilla audit FKs, which save() fills."""
        row.full_clean(exclude=["created_by", "updated_by"])

    def test_valid_optional_email_passes_clean(self):
        """Lead email can be stored as an empty string, so optional is allowed."""
        row = self._requirement()
        self._clean(row)

    def test_non_configurable_model_is_rejected(self):
        """Account did not opt in, so it cannot have overrides."""
        account = apps.get_model("accounts", "Account")
        row = self._requirement(
            content_type=HorillaContentType.objects.get_for_model(account),
            field_name="email",
        )
        with self.assertRaises(ValidationError) as ctx:
            self._clean(row)
        self.assertIn("content_type", ctx.exception.error_dict)

    def test_unknown_field_is_rejected(self):
        """A field that is not on the model cannot be configured."""
        row = self._requirement(field_name="not_a_real_field")
        with self.assertRaises(ValidationError) as ctx:
            self._clean(row)
        self.assertIn("field_name", ctx.exception.error_dict)

    def test_excluded_audit_field_is_rejected(self):
        """Bookkeeping columns are never configurable."""
        row = self._requirement(field_name="company")
        with self.assertRaises(ValidationError) as ctx:
            self._clean(row)
        self.assertIn("field_name", ctx.exception.error_dict)

    def test_relaxing_lead_status_is_rejected(self):
        """A non-nullable FK has nowhere to store an empty value."""
        row = self._requirement(field_name="lead_status", is_required=False)
        with self.assertRaises(ValidationError) as ctx:
            self._clean(row)
        self.assertIn("is_required", ctx.exception.error_dict)

    def test_requiring_lead_status_is_allowed(self):
        """Making a field required never needs an empty-value storage path."""
        row = self._requirement(field_name="lead_status", is_required=True)
        self._clean(row)

    def test_duplicate_override_for_same_company_is_rejected(self):
        """One override per model, field, and company."""
        self._requirement().save()
        duplicate = self._requirement()
        with self.assertRaises(ValidationError) as ctx:
            self._clean(duplicate)
        self.assertIn("__all__", ctx.exception.error_dict)

    def test_same_field_can_be_configured_for_another_company(self):
        """Overrides are company-scoped."""
        self._requirement().save()
        other = Company.objects.create(
            name="Other Co",
            email="other@example.com",
            country="GB",
        )
        row = self._requirement(company=other)
        self._clean(row)
        row.save()
        self.assertEqual(
            FieldRequirement.all_objects.filter(field_name="email").count(),
            2,
        )


class FieldRequirementResolverTests(TestCase):
    """Tests for get_field_requirements_for_model."""

    def setUp(self):
        self.company_a = Company.objects.create(
            name="Company A",
            email="a@example.com",
            country="US",
        )
        self.company_b = Company.objects.create(
            name="Company B",
            email="b@example.com",
            country="GB",
        )
        self.lead = apps.get_model("leads", "Lead")
        self.lead_ct = HorillaContentType.objects.get_for_model(self.lead)
        _activate_company(self.company_a)

    def tearDown(self):
        if hasattr(_thread_local, "request"):
            del _thread_local.request
        super().tearDown()

    def _create(self, company, field_name, is_required, **kwargs):
        return FieldRequirement.objects.create(
            content_type=self.lead_ct,
            field_name=field_name,
            is_required=is_required,
            company=company,
            **kwargs,
        )

    def test_returns_empty_for_unconfigured_model(self):
        """No rows means no overrides."""
        self.assertEqual(get_field_requirements_for_model(self.lead), {})

    def test_returns_empty_for_non_configurable_model(self):
        """Account is not opted in."""
        account = apps.get_model("accounts", "Account")
        self.assertEqual(get_field_requirements_for_model(account), {})

    def test_returns_empty_for_none(self):
        """A missing model is treated as unconfigured."""
        self.assertEqual(get_field_requirements_for_model(None), {})

    def test_optional_email_override_is_returned(self):
        """A valid relaxation is exposed as False."""
        self._create(self.company_a, "email", False)
        self.assertEqual(
            get_field_requirements_for_model(self.lead),
            {"email": False},
        )

    def test_required_override_is_returned(self):
        """An explicit required row is exposed as True."""
        self._create(self.company_a, "title", True)
        self.assertEqual(
            get_field_requirements_for_model(self.lead),
            {"title": True},
        )

    def test_overrides_are_scoped_to_the_active_company(self):
        """Company B does not see Company A's rows."""
        self._create(self.company_a, "email", False)
        self._create(self.company_b, "title", True)

        self.assertEqual(
            get_field_requirements_for_model(self.lead),
            {"email": False},
        )

        _activate_company(self.company_b)
        self.assertEqual(
            get_field_requirements_for_model(self.lead),
            {"title": True},
        )

    def test_inactive_rows_are_ignored(self):
        """Soft-deactivated overrides do not apply."""
        self._create(self.company_a, "email", False, is_active=False)
        self.assertEqual(get_field_requirements_for_model(self.lead), {})

    def test_unsafe_relaxation_is_dropped(self):
        """A stale row that relaxes a non-nullable FK is not applied."""
        FieldRequirement.all_objects.create(
            content_type=self.lead_ct,
            field_name="lead_status",
            is_required=False,
            company=self.company_a,
        )
        self.assertEqual(get_field_requirements_for_model(self.lead), {})

    def test_unknown_field_row_is_dropped(self):
        """A row pointing at a removed field is skipped."""
        FieldRequirement.all_objects.create(
            content_type=self.lead_ct,
            field_name="removed_field",
            is_required=False,
            company=self.company_a,
        )
        self.assertEqual(get_field_requirements_for_model(self.lead), {})

    def test_request_cache_avoids_seeing_mid_request_writes(self):
        """The first resolve on a request is reused until the request ends."""
        self._create(self.company_a, "email", False)
        first = get_field_requirements_for_model(self.lead)
        self._create(self.company_a, "title", True)
        second = get_field_requirements_for_model(self.lead)
        self.assertEqual(first, {"email": False})
        self.assertEqual(second, {"email": False})

        delattr(_thread_local.request, "_field_requirement_overrides")
        self.assertEqual(
            get_field_requirements_for_model(self.lead),
            {"email": False, "title": True},
        )
