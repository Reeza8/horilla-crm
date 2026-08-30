"""
Tests for horilla.contrib.generics.

Unit tests and integration tests for the horilla.contrib.generics app.
"""

# Standard library imports
from types import SimpleNamespace

# Third-party imports (Django)
from django import forms
from django.test import SimpleTestCase

# First party imports (Horilla)
from horilla.contrib.generics.forms.form_class_mixin import HorillaFormMixin
from horilla.core.exceptions import FieldDoesNotExist
from horilla.db import models


def _fake_model(**model_fields):
    """Build a stand-in model whose ``_meta.get_field`` serves ``model_fields``."""

    def get_field(name):
        """Return the named field or raise, mirroring Django's Options.get_field."""
        if name not in model_fields:
            raise FieldDoesNotExist(name)
        return model_fields[name]

    return SimpleNamespace(_meta=SimpleNamespace(get_field=get_field))


class _StubForm(HorillaFormMixin):
    """Database-free stand-in exercising the requiredness hooks in isolation."""

    def __init__(
        self, model, fields=None, instance=None, stored_files=None, overrides=None
    ):
        self._meta = SimpleNamespace(model=model)
        self.fields = fields or {}
        self.instance = instance
        self.stored_files = stored_files or {}
        self.form_data = {}
        # Stands in for the settings lookup, which would otherwise need the
        # database. Assigning the cached_property is enough to preempt it.
        self.field_requirement_overrides = overrides or {}


class IsFieldRequiredTests(SimpleTestCase):
    """Tests for HorillaFormMixin.is_field_required."""

    def test_required_follows_blank_on_model_field(self):
        """A field is required when the model declares blank=False."""
        model = _fake_model(
            email=models.EmailField(blank=False),
            city=models.CharField(blank=True),
        )
        form = _StubForm(model)

        self.assertTrue(form.is_field_required("email"))
        self.assertFalse(form.is_field_required("city"))

    def test_required_ignores_null_when_blank_is_false(self):
        """blank=False keeps the form field required even when null=True."""
        model = _fake_model(closed_on=models.DateField(null=True, blank=False))
        form = _StubForm(model)

        self.assertTrue(form.is_field_required("closed_on"))

    def test_falls_back_to_form_field_without_model_field(self):
        """Declared fields with no model counterpart keep their own flag."""
        model = _fake_model()
        form = _StubForm(
            model,
            fields={
                "state": forms.ChoiceField(choices=[], required=False),
                "token": forms.CharField(required=True),
            },
        )

        self.assertFalse(form.is_field_required("state"))
        self.assertTrue(form.is_field_required("token"))

    def test_subclass_can_relax_requiredness(self):
        """Overriding the hook is enough to change requiredness."""

        class _OptionalEmailForm(_StubForm):
            """Stub form that never requires email."""

            def is_field_required(self, field_name, field=None, model_field=None):
                """Relax email, defer to the default rule for everything else."""
                if field_name == "email":
                    return False
                return super().is_field_required(field_name, field, model_field)

        model = _fake_model(
            email=models.EmailField(blank=False),
            name=models.CharField(blank=False),
        )
        form = _OptionalEmailForm(model)

        self.assertFalse(form.is_field_required("email"))
        self.assertTrue(form.is_field_required("name"))


class IsFieldMandatoryTests(SimpleTestCase):
    """Tests for HorillaFormMixin.is_field_mandatory."""

    def test_mandatory_requires_both_null_and_blank_false(self):
        """Only a column rejecting empty values counts as mandatory."""
        model = _fake_model(
            name=models.CharField(null=False, blank=False),
            closed_on=models.DateField(null=True, blank=False),
            notes=models.TextField(null=False, blank=True),
        )
        form = _StubForm(model)

        self.assertTrue(form.is_field_mandatory("name"))
        self.assertFalse(form.is_field_mandatory("closed_on"))
        self.assertFalse(form.is_field_mandatory("notes"))

    def test_fallback_is_used_without_model_field(self):
        """An explicit fallback wins when there is no model field."""
        form = _StubForm(_fake_model(), fields={"token": forms.CharField()})

        self.assertFalse(form.is_field_mandatory("token", fallback=False))
        self.assertTrue(form.is_field_mandatory("token", fallback=True))

    def test_original_required_preferred_over_current_required(self):
        """Multi-step forms stash _original_required before relaxing checkboxes."""
        field = forms.BooleanField(required=False)
        field._original_required = True
        form = _StubForm(_fake_model(), fields={"agreed": field})

        self.assertTrue(form.is_field_mandatory("agreed"))

    def test_deprecated_alias_delegates(self):
        """_is_field_mandatory still resolves through the public hook."""
        model = _fake_model(name=models.CharField(null=False, blank=False))
        form = _StubForm(model)

        self.assertTrue(form._is_field_mandatory("name", None))


class ResolveFieldRequiredTests(SimpleTestCase):
    """Tests for HorillaFormMixin.resolve_field_required."""

    def test_boolean_fields_are_never_required(self):
        """A required checkbox would force the box to be ticked."""
        model = _fake_model(is_active=models.BooleanField(blank=False))
        form = _StubForm(model, fields={"is_active": forms.BooleanField()})

        self.assertFalse(form.resolve_field_required("is_active"))

    def test_file_field_stays_required_without_a_stored_value(self):
        """A blank=False file field with nothing uploaded stays required."""
        model = _fake_model(logo=models.FileField(blank=False))
        form = _StubForm(model, fields={"logo": forms.FileField()})

        self.assertTrue(form.resolve_field_required("logo"))

    def test_optional_file_field_with_stored_upload_is_not_required(self):
        """An already-uploaded optional file must not force a re-upload."""
        model = _fake_model(logo=models.FileField(blank=True))
        form = _StubForm(
            model,
            fields={"logo": forms.FileField()},
            stored_files={"logo": object()},
        )

        self.assertFalse(form.resolve_field_required("logo"))

    def test_non_model_field_keeps_its_own_flag(self):
        """Fields rebuilt by subclasses are left alone."""
        form = _StubForm(
            _fake_model(),
            fields={"state": forms.ChoiceField(choices=[], required=False)},
        )

        self.assertFalse(form.resolve_field_required("state"))

    def test_override_of_is_field_required_propagates(self):
        """Relaxing is_field_required must reach the step-level resolver.

        This is the seam the form layer relies on: overriding one hook has to
        change what the rendered form asks for, without touching call sites.
        """

        class _OptionalEmailForm(_StubForm):
            """Stub form that never requires email."""

            def is_field_required(self, field_name, field=None, model_field=None):
                """Relax email, defer to the default rule for everything else."""
                if field_name == "email":
                    return False
                return super().is_field_required(field_name, field, model_field)

        model = _fake_model(
            email=models.EmailField(null=False, blank=False),
            name=models.CharField(null=False, blank=False),
        )
        form = _OptionalEmailForm(
            model,
            fields={"email": forms.EmailField(), "name": forms.CharField()},
        )

        self.assertFalse(form.resolve_field_required("email"))
        self.assertTrue(form.resolve_field_required("name"))

    def test_relaxing_required_leaves_mandatory_untouched(self):
        """Requiredness and mandatoriness stay independent.

        Field permissions keep mandatory fields on the form so the row can be
        saved. Relaxing the form-level rule must not silently strip that
        protection, or a readonly field could be dropped and break the insert.
        """

        class _OptionalEmailForm(_StubForm):
            """Stub form that never requires email."""

            def is_field_required(self, field_name, field=None, model_field=None):
                """Relax email at the form level only."""
                if field_name == "email":
                    return False
                return super().is_field_required(field_name, field, model_field)

        model = _fake_model(email=models.EmailField(null=False, blank=False))
        form = _OptionalEmailForm(model, fields={"email": forms.EmailField()})

        self.assertFalse(form.is_field_required("email"))
        self.assertTrue(form.is_field_mandatory("email"))


class ConfiguredRequirementTests(SimpleTestCase):
    """Tests for admin-configured requiredness overrides."""

    def test_override_can_relax_a_required_field(self):
        """A stored override wins over the model's blank=False."""
        model = _fake_model(email=models.EmailField(blank=False))
        form = _StubForm(model, overrides={"email": False})

        self.assertFalse(form.is_field_required("email"))

    def test_override_can_require_an_optional_field(self):
        """Tightening is always allowed; the column already accepts a value."""
        model = _fake_model(city=models.CharField(blank=True))
        form = _StubForm(model, overrides={"city": True})

        self.assertTrue(form.is_field_required("city"))

    def test_fields_without_an_override_are_untouched(self):
        """Configuring one field must not disturb its neighbours."""
        model = _fake_model(
            email=models.EmailField(blank=False),
            city=models.CharField(blank=True),
        )
        form = _StubForm(model, overrides={"email": False})

        self.assertFalse(form.is_field_required("email"))
        self.assertFalse(form.is_field_required("city"))

    def test_override_does_not_change_mandatoriness(self):
        """Relaxing a form field must not claim the column accepts NULL.

        Field permissions rely on is_field_mandatory to keep a field on the
        form so the row can be saved; an override must not weaken that.
        """
        model = _fake_model(email=models.EmailField(null=False, blank=False))
        form = _StubForm(model, overrides={"email": False})

        self.assertTrue(form.is_field_mandatory("email"))

    def test_override_reaches_the_step_resolver(self):
        """Multi-step forms resolve per step and must honour the override."""
        model = _fake_model(email=models.EmailField(blank=False))
        form = _StubForm(
            model,
            fields={"email": forms.EmailField()},
            overrides={"email": False},
        )

        self.assertFalse(form.resolve_field_required("email"))

    def test_apply_overrides_updates_only_configured_fields(self):
        """Single-step forms apply overrides without re-deriving every field."""
        model = _fake_model(
            email=models.EmailField(blank=False),
            city=models.CharField(blank=True),
        )
        email_field = forms.EmailField(required=True)
        city_field = forms.CharField(required=False)
        form = _StubForm(
            model,
            fields={"email": email_field, "city": city_field},
            overrides={"email": False},
        )

        form.apply_field_requirement_overrides()

        self.assertFalse(email_field.required)
        self.assertFalse(city_field.required)

    def test_apply_overrides_ignores_fields_absent_from_the_form(self):
        """A field hidden by permissions must not be resurrected."""
        model = _fake_model(email=models.EmailField(blank=False))
        form = _StubForm(model, fields={}, overrides={"email": False})

        form.apply_field_requirement_overrides()

        self.assertEqual(form.fields, {})

    def test_booleans_stay_optional_despite_an_override(self):
        """A required checkbox would force the box to be ticked."""
        model = _fake_model(is_active=models.BooleanField(blank=False))
        form = _StubForm(
            model,
            fields={"is_active": forms.BooleanField()},
            overrides={"is_active": True},
        )

        self.assertFalse(form.resolve_field_required("is_active"))
