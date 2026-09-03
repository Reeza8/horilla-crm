"""
Tests for the field requirements app.

Covers feature-registry opt-in, the safety rules that decide whether a field
may be made optional without breaking inserts, the settings UI that stores
per-company overrides, and FormExtension discovery that applies those
overrides on opted-in create and edit forms.
"""

# Standard library imports
import importlib
from pathlib import Path
from types import SimpleNamespace

# Third-party imports (Django)
from django.conf import settings
from django.contrib.auth.models import Permission
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.test import SimpleTestCase, TestCase
from login_history.models import post_login, post_logout

# First party imports (Horilla)
from horilla.apps import apps
from horilla.auth.models import User
from horilla.contrib.core.models import Company, HorillaContentType
from horilla.contrib.field_requirements.extensions import (
    iter_configurable_model_forms,
    register_discovered_form_extensions,
)
from horilla.contrib.field_requirements.forms import (
    FieldRequirementForm,
    get_field_choices,
)
from horilla.contrib.field_requirements.menu import FieldRequirementSettings
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
from horilla.extension.forms import resolve_form_class
from horilla.extension.forms.bootstrap import apply_form_extensions
from horilla.extension.forms.registry import FORM_EXTENSION_REGISTRY
from horilla.menu.settings_menu import settings_registry
from horilla.registry.feature import FEATURE_CONFIG, FEATURE_REGISTRY
from horilla.urls import reverse


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

    def test_reverse_accessors_include_the_app_label(self):
        """Avoid clashing with another FieldRequirement that uses %(class)s_*."""
        self.assertTrue(hasattr(Company, "field_requirements_fieldrequirement_set"))
        self.assertEqual(
            FieldRequirement._meta.get_field("created_by").remote_field.related_name,
            "field_requirements_fieldrequirement_created",
        )


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


class FieldRequirementUrlTests(SimpleTestCase):
    """Settings URLs live on the contrib app, not on core."""

    def test_settings_urls_resolve_under_the_app_namespace(self):
        """The settings page is served from /field-requirements/."""
        self.assertEqual(
            reverse("field_requirements:field_requirement_view"),
            "/field-requirements/",
        )
        self.assertEqual(
            reverse("field_requirements:field_requirement_field_choices"),
            "/field-requirements/field-choices/",
        )

    def test_core_urls_do_not_include_field_requirement_routes(self):
        """Stage 3 must not put the settings page back on core."""
        from horilla.contrib.core import urls as core_urls

        names = [getattr(pattern, "name", None) for pattern in core_urls.urlpatterns]
        self.assertNotIn("field_requirement_view", names)
        self.assertNotIn("field_requirement_create_form", names)

    def test_settings_menu_is_registered_on_this_app(self):
        """The menu is a dedicated settings section, not an edit to core.menu."""
        self.assertIn(FieldRequirementSettings, settings_registry)
        self.assertEqual(
            FieldRequirementSettings.items[0]["perm"],
            "field_requirements.view_fieldrequirement",
        )


class FieldRequirementFormTests(TestCase):
    """Tests for the settings form and field picker labels."""

    def setUp(self):
        self.lead = apps.get_model("leads", "Lead")
        self.lead_ct = HorillaContentType.objects.get_for_model(self.lead)
        self.account = apps.get_model("accounts", "Account")
        self.account_ct = HorillaContentType.objects.get_for_model(self.account)

    def test_field_picker_lists_lead_fields_and_marks_unsafe_ones(self):
        """Lead email is offered; Lead Stage is labelled always required."""
        choices = dict(get_field_choices(self.lead))
        self.assertIn("email", choices)
        self.assertIn("first_name", choices)
        self.assertIn("lead_status", choices)
        self.assertIn("always required", str(choices["lead_status"]).lower())
        self.assertNotIn("always required", str(choices["email"]).lower())

    def test_form_model_choices_are_limited_to_opted_in_models(self):
        """Account did not opt in, so it is not a model the admin can pick."""
        form = FieldRequirementForm()
        pks = set(form.fields["content_type"].queryset.values_list("pk", flat=True))
        self.assertIn(self.lead_ct.pk, pks)
        self.assertNotIn(self.account_ct.pk, pks)

    def test_optional_email_is_valid(self):
        """The form accepts making Lead email optional."""
        form = FieldRequirementForm(
            data={
                "content_type": self.lead_ct.pk,
                "field_name": "email",
                "is_required": False,
            }
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_relaxing_lead_status_is_rejected(self):
        """The form refuses to make Lead Stage optional."""
        form = FieldRequirementForm(
            data={
                "content_type": self.lead_ct.pk,
                "field_name": "lead_status",
                "is_required": False,
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("is_required", form.errors)


def _create_company_and_user(*, superuser=True):
    """Create a company-scoped user for settings-page request tests."""
    company = Company.objects.create(
        name="Acme",
        email="acme@example.com",
        country="US",
    )
    create = User.objects.create_superuser if superuser else User.objects.create_user
    user = create(
        username="admin" if superuser else "staff",
        email="admin@example.com" if superuser else "staff@example.com",
        password="pass",
        company=company,
    )
    return company, user


class FieldRequirementViewTests(TestCase):
    """HTTP tests for the settings page, field picker, and create flow."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # django-login-history reads request.META['HTTP_USER_AGENT'] on
        # login/logout. Django's test client builds a bare HttpRequest, so
        # those signals KeyError unless they are disconnected here.
        user_logged_in.disconnect(post_login)
        user_logged_out.disconnect(post_logout)

    @classmethod
    def tearDownClass(cls):
        user_logged_in.connect(post_login)
        user_logged_out.connect(post_logout)
        super().tearDownClass()

    def setUp(self):
        self.company, self.user = _create_company_and_user()
        self.lead = apps.get_model("leads", "Lead")
        self.lead_ct = HorillaContentType.objects.get_for_model(self.lead)
        self.client.force_login(self.user)

    def _htmx(self):
        return {"HTTP_HX_REQUEST": "true"}

    def test_anonymous_user_is_sent_to_login(self):
        """The settings page requires an authenticated user."""
        self.client.logout()
        response = self.client.get(reverse("field_requirements:field_requirement_view"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response.url)

    def test_user_without_permission_is_denied(self):
        """View permission is required to open the settings page."""
        _, staff = _create_company_and_user(superuser=False)
        staff.username = "viewer"
        staff.email = "viewer@example.com"
        staff.save()
        self.client.force_login(staff)
        response = self.client.get(reverse("field_requirements:field_requirement_view"))
        self.assertContains(response, "Permission Denied", status_code=200)

    def test_user_with_view_permission_can_open_the_page(self):
        """A non-superuser with the view permission sees the settings shell."""
        _, staff = _create_company_and_user(superuser=False)
        staff.username = "allowed"
        staff.email = "allowed@example.com"
        staff.save()
        staff.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="field_requirements",
                codename="view_fieldrequirement",
            )
        )
        self.client.force_login(staff)
        response = self.client.get(reverse("field_requirements:field_requirement_view"))
        self.assertContains(response, "field-requirement-view")

    def test_settings_page_renders_the_shell(self):
        """The page includes the HTMX shell the settings sidebar swaps in."""
        response = self.client.get(reverse("field_requirements:field_requirement_view"))
        self.assertContains(response, 'id="field-requirement-view"')
        self.assertContains(
            response, reverse("field_requirements:field_requirement_nav_view")
        )
        self.assertContains(
            response, reverse("field_requirements:field_requirement_list_view")
        )

    def test_list_without_htmx_is_rejected(self):
        """Navbar and list fragments are HTMX-only."""
        response = self.client.get(
            reverse("field_requirements:field_requirement_list_view")
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Method Not Allowed")

    def test_list_view_includes_existing_override(self):
        """A saved Lead email override appears on the list."""
        row = FieldRequirement.objects.create(
            content_type=self.lead_ct,
            field_name="email",
            is_required=False,
            company=self.company,
        )
        response = self.client.get(
            reverse("field_requirements:field_requirement_list_view"),
            **self._htmx(),
        )
        self.assertContains(response, "Email")
        self.assertContains(response, "Optional")
        self.assertContains(response, str(row.get_edit_url()))
        self.assertContains(response, str(row.get_delete_url()))

    def test_field_choices_list_lead_fields(self):
        """Selecting Lead fills the field picker with Lead columns."""
        response = self.client.get(
            reverse("field_requirements:field_requirement_field_choices"),
            {"content_type": self.lead_ct.pk},
            **self._htmx(),
        )
        self.assertContains(response, 'value="email"')
        self.assertContains(response, 'value="first_name"')
        self.assertContains(response, 'value="lead_status"')
        self.assertContains(response, "always required")

    def test_create_optional_lead_email(self):
        """Posting Lead → Email → Optional stores the override for the company."""
        response = self.client.post(
            reverse("field_requirements:field_requirement_create_form"),
            {
                "content_type": self.lead_ct.pk,
                "field_name": "email",
            },
            **self._htmx(),
        )
        self.assertEqual(response.status_code, 200)
        row = FieldRequirement.objects.get(
            content_type=self.lead_ct, field_name="email", company=self.company
        )
        self.assertFalse(row.is_required)

    def test_create_rejects_optional_lead_status(self):
        """Posting Lead Stage as optional is refused and stores nothing."""
        response = self.client.post(
            reverse("field_requirements:field_requirement_create_form"),
            {
                "content_type": self.lead_ct.pk,
                "field_name": "lead_status",
            },
            **self._htmx(),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "empty value")
        self.assertFalse(
            FieldRequirement.objects.filter(field_name="lead_status").exists()
        )

    def test_settings_page_is_linked_from_the_settings_shell(self):
        """Settings → Field Requirements is in the sidebar for a permitted user."""
        response = self.client.get(reverse("core:settings_view"))
        self.assertContains(
            response, reverse("field_requirements:field_requirement_view")
        )
        self.assertContains(response, "Field Requirements")


def _python_sources_under(*relative_roots):
    """Yield ``.py`` files under ``settings.BASE_DIR`` / each relative root."""
    base = Path(settings.BASE_DIR)
    for relative in relative_roots:
        root = base / relative
        if not root.exists():
            continue
        yield from root.rglob("*.py")


def _is_crm_model_module(path):
    """Return True when ``path`` is a CRM model module, not forms or views."""
    try:
        relative = path.relative_to(Path(settings.BASE_DIR) / "horilla_crm")
    except ValueError:
        return False
    parts = relative.parts
    return "models" in parts[:-1] or relative.name == "models.py"


class IsolationFromPlatformTests(SimpleTestCase):
    """Grep bar: this feature must not leak into core, generics, or CRM models."""

    def test_core_and_generics_do_not_mention_field_requirement(self):
        """``horilla.contrib.core`` and ``generics`` stay unaware of this app."""
        hits = []
        for path in _python_sources_under(
            "horilla/contrib/core",
            "horilla/contrib/generics",
        ):
            text = path.read_text(encoding="utf-8")
            if "field_requirement" in text:
                hits.append(str(path.relative_to(settings.BASE_DIR)))
        self.assertEqual(hits, [])

    def test_crm_model_modules_do_not_mention_field_requirement(self):
        """Lead/Opportunity opt in from registration.py, not from model files."""
        hits = []
        for path in _python_sources_under("horilla_crm"):
            if not _is_crm_model_module(path):
                continue
            text = path.read_text(encoding="utf-8")
            if "field_requirement" in text:
                hits.append(str(path.relative_to(settings.BASE_DIR)))
        self.assertEqual(hits, [])

    def test_generics_forms_do_not_import_this_app(self):
        """Form mixins are unchanged; overrides ride in through FormExtension."""
        import horilla.contrib.generics.forms as generics_forms

        source = Path(generics_forms.__file__).read_text(encoding="utf-8")
        self.assertNotIn("field_requirement", source)


class FieldRequirementFormExtensionTests(TestCase):
    """Tests that stored overrides actually change Lead and Opportunity forms."""

    def setUp(self):
        self.company = Company.objects.create(
            name="Acme",
            email="acme@example.com",
            country="US",
        )
        self.other_company = Company.objects.create(
            name="Other Co",
            email="other@example.com",
            country="GB",
        )
        self.user = User.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="pass",
            company=self.company,
        )
        self.lead = apps.get_model("leads", "Lead")
        self.opportunity = apps.get_model("opportunities", "Opportunity")
        self.lead_ct = HorillaContentType.objects.get_for_model(self.lead)
        self.opportunity_ct = HorillaContentType.objects.get_for_model(self.opportunity)
        self.status = apps.get_model("leads", "LeadStatus").objects.create(
            name="New",
            order=1,
            probability=10,
            company=self.company,
        )
        _activate_company(self.company)
        register_discovered_form_extensions()
        apply_form_extensions(force=True)

    def tearDown(self):
        if hasattr(_thread_local, "request"):
            del _thread_local.request
        super().tearDown()

    def _override(self, field_name, is_required, *, model_ct=None, company=None):
        return FieldRequirement.objects.create(
            content_type=model_ct or self.lead_ct,
            field_name=field_name,
            is_required=is_required,
            company=company or self.company,
        )

    def _lead_single_form(self, data=None):
        from horilla_crm.leads.forms import LeadSingleForm

        return resolve_form_class(LeadSingleForm)(data=data)

    def _lead_multi_form(self, *, step, data=None):
        from horilla_crm.leads.forms import LeadFormClass

        return resolve_form_class(LeadFormClass)(data=data, step=step)

    def _lead_payload(self, email=""):
        return {
            "first_name": "Ada",
            "last_name": "Lovelace",
            "email": email,
            "lead_source": "website",
            "lead_status": self.status.pk,
            "lead_company": "Analytical Engines",
            "industry": "education",
            "country": "US",
            "lead_owner": self.user.pk,
        }

    def test_discovery_registers_lead_and_opportunity_forms_only(self):
        """Lead/Opportunity create-edit forms are extended; Account and LeadStatus are not."""
        discovered = {
            f"{form.__module__}.{form.__name__}"
            for form in iter_configurable_model_forms()
        }
        self.assertIn("horilla_crm.leads.forms.LeadSingleForm", discovered)
        self.assertIn("horilla_crm.leads.forms.LeadFormClass", discovered)
        self.assertIn(
            "horilla_crm.opportunities.forms.OpportunitySingleForm", discovered
        )
        self.assertIn(
            "horilla_crm.opportunities.forms.OpportunityFormClass", discovered
        )
        self.assertNotIn("horilla_crm.leads.forms.LeadStatusForm", discovered)
        self.assertNotIn("horilla_crm.accounts.forms.AccountFormClass", discovered)

        self.assertIn("horilla_crm.leads.forms.LeadSingleForm", FORM_EXTENSION_REGISTRY)
        self.assertNotIn(
            "horilla_crm.leads.forms.LeadStatusForm", FORM_EXTENSION_REGISTRY
        )
        self.assertNotIn(
            "horilla_crm.accounts.forms.AccountFormClass", FORM_EXTENSION_REGISTRY
        )

    def test_resolve_returns_a_composed_lead_form(self):
        """Views call resolve_form_class; the result is the composed subclass."""
        from horilla_crm.leads.forms import LeadFormClass, LeadSingleForm

        single = resolve_form_class(LeadSingleForm)
        multi = resolve_form_class(LeadFormClass)
        self.assertTrue(getattr(single, "__horilla_composed__", False))
        self.assertTrue(getattr(multi, "__horilla_composed__", False))
        self.assertTrue(single.__name__.endswith("Extended"))
        self.assertIsNot(single, LeadSingleForm)

    def test_email_stays_required_without_an_override(self):
        """Lead.email is blank=False, so the form still requires it by default."""
        form = self._lead_single_form()
        self.assertTrue(form.fields["email"].required)

        bound = self._lead_single_form(data=self._lead_payload(email=""))
        self.assertFalse(bound.is_valid())
        self.assertIn("email", bound.errors)

    def test_optional_email_is_not_required_on_lead_single_form(self):
        """A company-scoped optional email row drops required on LeadSingleForm."""
        self._override("email", False)
        form = self._lead_single_form()
        self.assertFalse(form.fields["email"].required)
        self.assertNotIn("required", form.fields["email"].widget.attrs)

    def test_optional_email_allows_an_empty_value_to_validate(self):
        """Empty email must pass both form and model validation when optional."""
        self._override("email", False)
        form = self._lead_single_form(data=self._lead_payload(email=""))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data.get("email") or "", "")

    def test_optional_email_does_not_apply_to_another_company(self):
        """Company B still requires email when only Company A stored an override."""
        self._override("email", False)
        _activate_company(self.other_company)
        form = self._lead_single_form()
        self.assertTrue(form.fields["email"].required)

    def test_optional_email_applies_to_the_multi_step_lead_form(self):
        """LeadFormClass is discovered the same way as the single-step form."""
        self._override("email", False)
        form = self._lead_multi_form(step=1)
        self.assertFalse(form.fields["email"].required)

    def test_required_override_does_not_rerequire_hidden_wizard_steps(self):
        """Title is on step 1; a required override must not break step 2."""
        self._override("title", True)
        step_two = self._lead_multi_form(step=2)
        self.assertIn("title", step_two._step_hidden_fields)
        self.assertFalse(step_two.fields["title"].required)

        step_one = self._lead_multi_form(step=1)
        self.assertTrue(step_one.fields["title"].required)

    def test_optional_email_on_step_one_stays_optional_on_later_steps(self):
        """Hidden wizard fields stay optional when the override relaxes them."""
        self._override("email", False)
        form = self._lead_multi_form(step=2)
        self.assertFalse(form.fields["email"].required)

    def test_required_description_override_on_opportunity_form(self):
        """A blank=True field can be made required without touching the model."""
        self._override(
            "description",
            True,
            model_ct=self.opportunity_ct,
        )
        from horilla_crm.opportunities.forms import OpportunitySingleForm

        form = resolve_form_class(OpportunitySingleForm)()
        self.assertTrue(form.fields["description"].required)

    def test_opportunity_email_override_does_not_appear_on_create_form(self):
        """Opportunity create/edit forms exclude email, so the override is a no-op there."""
        self._override(
            "email",
            False,
            model_ct=self.opportunity_ct,
        )
        from horilla_crm.opportunities.forms import OpportunitySingleForm

        form = resolve_form_class(OpportunitySingleForm)()
        self.assertNotIn("email", form.fields)

    def test_optional_email_lead_saves_to_the_database(self):
        """An optional empty email must persist, not just pass form.is_valid()."""
        self._override("email", False)
        form = self._lead_single_form(data=self._lead_payload(email=""))
        self.assertTrue(form.is_valid(), form.errors)
        lead = form.save(commit=False)
        lead.company = self.company
        lead.created_by = self.user
        lead.updated_by = self.user
        lead.save()
        saved = self.lead.all_objects.get(pk=lead.pk)
        self.assertEqual(saved.email, "")
        self.assertEqual(saved.first_name, "Ada")

    def test_lead_without_override_cannot_be_saved_with_empty_email(self):
        """Default Lead email still cannot be stored empty."""
        form = self._lead_single_form(data=self._lead_payload(email=""))
        self.assertFalse(form.is_valid())
        self.assertFalse(self.lead.all_objects.filter(first_name="Ada").exists())

    def _login_client(self):
        """Log in through the test client and point it at this company."""
        user_logged_in.disconnect(post_login)
        user_logged_out.disconnect(post_logout)
        self.addCleanup(user_logged_in.connect, post_login)
        self.addCleanup(user_logged_out.connect, post_logout)
        self.client.force_login(self.user)
        session = self.client.session
        session["active_company_id"] = self.company.pk
        session.save()

    def _lead_create(self, method, data=None):
        """Hit the Lead single-create view the way the UI does (HTMX + section)."""
        url = reverse("leads:leads_create_single") + "?section=sales"
        headers = {"HTTP_HX_REQUEST": "true"}
        if method == "get":
            return self.client.get(url, **headers)
        return self.client.post(url, data, **headers)

    def test_create_view_uses_composed_form_with_optional_email(self):
        """The Lead create view resolves the FormExtension and drops email required."""
        self._override("email", False)
        self._login_client()
        response = self._lead_create("get")
        self.assertEqual(response.status_code, 200)
        form = response.context["form"]
        self.assertTrue(getattr(form.__class__, "__horilla_composed__", False))
        self.assertFalse(form.fields["email"].required)

    def test_create_view_saves_a_lead_without_email_when_optional(self):
        """Posting the real create view with empty email stores the lead."""
        self._override("email", False)
        self._login_client()
        response = self._lead_create("post", self._lead_payload(email=""))
        self.assertNotEqual(response.status_code, 500)
        saved = self.lead.all_objects.filter(first_name="Ada", last_name="Lovelace")
        self.assertEqual(saved.count(), 1, response.content[:2000])
        self.assertEqual(saved.get().email, "")

    def test_create_view_still_requires_email_without_an_override(self):
        """The same create view rejects empty email when nothing is configured."""
        self._login_client()
        response = self._lead_create("post", self._lead_payload(email=""))
        self.assertFalse(
            self.lead.all_objects.filter(
                first_name="Ada", last_name="Lovelace"
            ).exists(),
            response.content[:2000],
        )
