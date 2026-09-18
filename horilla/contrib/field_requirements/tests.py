"""
Tests for the field requirements app.

Covers the model-agnostic mechanism: the safety rules that decide whether a
field may be made optional without breaking inserts, which fields are
configurable on an opted-in model, the settings UI routes/menu, and
isolation from the rest of the platform.

Tests that exercise this mechanism against a specific opted-in app's real
models and forms live in that app's own test module instead, so this file
never hardcodes another app's models, fields, or import paths.
"""

# Standard library imports
from pathlib import Path

# Third-party imports (Django)
from django.conf import settings
from django.test import SimpleTestCase

# First party imports (Horilla)
from horilla.apps import apps
from horilla.contrib.field_requirements.menu import FieldRequirementSettings
from horilla.contrib.field_requirements.registry import (
    can_relax_requirement,
    get_configurable_fields,
    get_relax_blocked_reason,
    is_requirement_configurable,
)
from horilla.db import models
from horilla.menu.settings_menu import settings_registry
from horilla.urls import reverse


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


class ConfigurableFieldsTests(SimpleTestCase):
    """Tests for which fields appear as configurable on an opted-in model."""

    def test_unregistered_model_has_no_configurable_fields(self):
        """Models that did not opt in expose no fields."""
        content_type = apps.get_model("core", "HorillaContentType")
        self.assertEqual(get_configurable_fields(content_type), [])

    def test_object_without_meta_is_not_configurable(self):
        """Guards the registry against being handed a non-model."""
        self.assertFalse(is_requirement_configurable(object()))

    def test_bookkeeping_fields_are_excluded(self):
        """Audit columns and the primary key must never be configurable."""
        from horilla.contrib.field_requirements.registry import get_excluded_fields

        class _WithExcludes:
            """Stand-in model carrying the usual exclude list."""

            field_permissions_exclude = ["company", "created_at"]
            requirement_config_exclude = ["computed_score"]

        excluded = get_excluded_fields(_WithExcludes)

        self.assertIn("id", excluded)
        self.assertIn("pk", excluded)
        self.assertIn("company", excluded)
        self.assertIn("created_at", excluded)
        self.assertIn("computed_score", excluded)


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
        """CRM models opt in from registration.py, not from model files."""
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
