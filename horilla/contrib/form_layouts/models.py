"""
This module defines the configurable form layout model.

A ``FormLayoutField`` row records, for one company, whether one field of an
opted-in model is shown on that model's form and at which position. The rows
for a model together form its layout; a model without rows keeps the form its
app ships with. The layout is offered as an opt-in "Custom Layout" form mode
on both create and edit requests — see ``view_extensions.py`` — and never
changes the default form itself.
"""

# Third-party imports (Django)
from django.conf import settings

# First party imports (Horilla)
from horilla.contrib.core.models import Company, HorillaContentType, HorillaCoreModel
from horilla.db import models
from horilla.utils.translation import gettext_lazy as _

# Local imports
from .registry import limit_content_types


class FormLayoutField(HorillaCoreModel):
    """
    Per-company position and visibility of one field on a form.

    Only affects which fields are rendered when the "Custom Layout" form mode
    is active (an opt-in alongside the default form, on both create and edit
    requests) — the default form is never affected. A field the form
    requires is shown regardless of ``is_visible`` so a saved layout can
    never block a save; removing an optional field never touches its stored
    value on an existing record (see ``view_extensions.py``).

    Reverse accessors include the app label so they do not clash with another
    model of the same class name (HorillaCoreModel defaults to ``%(class)s_*``).
    """

    content_type = models.ForeignKey(
        HorillaContentType,
        on_delete=models.CASCADE,
        limit_choices_to=limit_content_types,
        related_name="%(app_label)s_%(class)s_set",
        verbose_name=_("Model"),
    )
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="%(app_label)s_%(class)s_set",
        verbose_name=_("Company"),
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="%(app_label)s_%(class)s_created",
        verbose_name=_("Created By"),
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="%(app_label)s_%(class)s_updated",
        verbose_name=_("Updated By"),
    )
    field_name = models.CharField(max_length=255, verbose_name=_("Field"))
    is_visible = models.BooleanField(
        default=True,
        verbose_name=_("Show on Form"),
    )
    sequence = models.PositiveIntegerField(default=0, verbose_name=_("Sequence"))

    class Meta:
        """
        Meta options for the FormLayoutField model.
        """

        verbose_name = _("Form Layout Field")
        verbose_name_plural = _("Form Layout Fields")
        unique_together = (("content_type", "field_name", "company"),)
        ordering = ["content_type__model", "sequence", "pk"]

    def __str__(self):
        return f"{self.content_type} - {self.field_name}"
