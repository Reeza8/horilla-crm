"""
Tests for horilla.contrib.core.

Covers the safety rules behind configurable field requiredness, which decide
whether a field may be made optional without breaking inserts.
"""

# Third-party imports (Django)
from django.test import SimpleTestCase

# First party imports (Horilla)
from horilla.db import models
from horilla.registry.field_requirement_registry import (
    can_relax_requirement,
    configurable_field_requirements,
    get_excluded_fields,
    get_relax_blocked_reason,
    is_requirement_configurable,
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


class RequirementRegistryTests(SimpleTestCase):
    """Tests for the opt-in registry of configurable models."""

    def test_unregistered_model_is_not_configurable(self):
        """Models must opt in explicitly."""

        class _Unregistered:
            """Stand-in for a model that never opted in."""

            class _meta:  # noqa: N801 - mimics Django's Meta accessor
                """Minimal meta providing the label the registry reads."""

                label_lower = "tests.unregistered"

        self.assertFalse(is_requirement_configurable(_Unregistered))

    def test_registered_model_is_configurable(self):
        """The decorator records the model and returns it unchanged."""

        class _Registered:
            """Stand-in for a model that opted in."""

            class _meta:  # noqa: N801 - mimics Django's Meta accessor
                """Minimal meta providing the label the registry reads."""

                label_lower = "tests.registered"

        returned = configurable_field_requirements(_Registered)

        self.assertIs(returned, _Registered)
        self.assertTrue(is_requirement_configurable(_Registered))

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
