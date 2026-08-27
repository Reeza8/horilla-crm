"""Models for Horilla platform Cadence (Task/Call/Email)."""

# Third-party imports (Django)
from django.conf import settings

from horilla.contrib.activity.models import Activity
from horilla.contrib.core.models import HorillaContentType, HorillaCoreModel
from horilla.contrib.mail.models import HorillaMailTemplate
from horilla.contrib.utils.methods import render_template
from horilla.core.exceptions import ValidationError

# First party imports (Horilla)
from horilla.db import models
from horilla.db.models import Q
from horilla.registry.limiters import limit_content_types
from horilla.registry.permission_registry import permission_exempt_model
from horilla.urls import reverse_lazy
from horilla.utils.choices import OPERATOR_CHOICES
from horilla.utils.translation import gettext_lazy as _


class Cadence(HorillaCoreModel):
    """Configurable cadence with ordered steps."""

    name = models.CharField(max_length=255, verbose_name=_("Name"))
    module = models.ForeignKey(
        HorillaContentType,
        on_delete=models.PROTECT,
        verbose_name=_("Module"),
        limit_choices_to=limit_content_types("cadence_models"),
        help_text=_("Target module"),
    )
    description = models.TextField(blank=True, null=True, verbose_name=_("Description"))

    class Meta:
        """Meta class for Cadence"""

        verbose_name = _("Cadence")
        verbose_name_plural = _("Cadences")
        ordering = ["-created_at"]

    def get_edit_url(self):
        """Return the URL for editing this cadence."""

        return reverse_lazy("cadences:cadence_update_view", kwargs={"pk": self.pk})

    def get_delete_url(self):
        """Return the URL for deleting this cadence."""

        return reverse_lazy("cadences:cadence_delete_view", kwargs={"pk": self.pk})

    def get_detail_url(self):
        """Return the URL for viewing this cadence."""

        return reverse_lazy("cadences:cadence_detail_view", kwargs={"pk": self.pk})

    def is_active_col(self):
        """Return HTML for active status column."""
        html = render_template(path="is_active_col.html", context={"instance": self})

        return html

    def _get_default_followup_number(self):
        """Return the next follow-up stage: lowest gap in 1..max+1, else max+1."""
        if not self.pk:
            return 1
        numbers = set(self.followups.values_list("followup_number", flat=True))
        if not numbers:
            return 1
        max_n = max(numbers)
        for n in range(1, max_n + 2):
            if n not in numbers:
                return n
        return max_n + 1

    def get_add_followup_url(self):
        """Return URL for add-followup modal with best default bucket."""
        followup_number = self._get_default_followup_number()
        return (
            f"{reverse_lazy('cadences:cadence_followup_create_view', kwargs={'cadence_pk': self.pk})}"
            f"?followup_number={followup_number}"
        )


@permission_exempt_model
class CadenceCondition(HorillaCoreModel):
    """Condition for cadence steps."""

    cadence = models.ForeignKey(
        Cadence,
        on_delete=models.CASCADE,
        related_name="conditions",
        verbose_name=_("Cadence"),
    )
    field = models.CharField(max_length=100, verbose_name=_("Field Name"))
    operator = models.CharField(
        max_length=50, choices=OPERATOR_CHOICES, verbose_name=_("Operator")
    )
    value = models.CharField(max_length=255, blank=True, verbose_name=_("Value"))
    logical_operator = models.CharField(
        max_length=3,
        choices=[("and", _("AND")), ("or", _("OR"))],
        default="and",
        verbose_name=_("Logical Operator"),
    )
    order = models.PositiveIntegerField(default=0, verbose_name=_("Order"))

    class Meta:
        """Meta class for CadenceCondition"""

        verbose_name = _("Cadence Condition")
        verbose_name_plural = _("Cadence Conditions")


class CadenceFollowUp(HorillaCoreModel):
    """Follow-up action in a cadence bucket (task/call/email)."""

    FOLLOWUP_TYPE_CHOICES = [
        ("task", _("Task")),
        ("call", _("Call")),
        ("email", _("Email")),
    ]
    PREVIOUS_STATUS_CHOICES = tuple(
        list(Activity.STATUS_CHOICES) + [("overdue", _("Overdue"))]
    )
    DO_THIS_UNIT_CHOICES = [
        ("immediately", _("Immediately")),
        ("minute", _("Minute")),
        ("hour", _("Hour")),
        ("day", _("Day")),
        ("month", _("Month")),
    ]

    cadence = models.ForeignKey(
        Cadence,
        on_delete=models.CASCADE,
        related_name="followups",
        verbose_name=_("Cadence"),
    )
    followup_number = models.PositiveSmallIntegerField(
        default=1,
        verbose_name=_("Follow Up"),
        help_text=_("Stage number (1 = first follow-up)."),
    )
    followup_type = models.CharField(
        max_length=20,
        choices=FOLLOWUP_TYPE_CHOICES,
        verbose_name=_("Follow Up Type"),
    )
    order = models.PositiveIntegerField(default=0, verbose_name=_("Order"))
    branch_from = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="branch_children",
        verbose_name=_("Branched From"),
        help_text=_(
            "Set when this step was created from a specific parent card’s + (next stage)."
        ),
    )

    do_this_unit = models.CharField(
        max_length=20,
        choices=DO_THIS_UNIT_CHOICES,
        default="immediately",
        verbose_name=_("Do This"),
    )
    do_this_value = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_("Do This Value"),
        help_text=_("Required for minute/hour/day/month."),
    )
    previous_status = models.CharField(
        max_length=30,
        choices=PREVIOUS_STATUS_CHOICES,
        null=True,
        blank=True,
        verbose_name=_("After Previous Status Is"),
        help_text=_("Required from follow up 2 onwards."),
    )

    # Task
    subject = models.CharField(
        max_length=255, null=True, blank=True, verbose_name=_("Subject")
    )
    due_after_days = models.PositiveIntegerField(
        null=True, blank=True, verbose_name=_("Trigger Date + Days")
    )
    task_status = models.CharField(
        max_length=20,
        choices=Activity.STATUS_CHOICES,
        null=True,
        blank=True,
        verbose_name=_("Status"),
    )
    task_priority = models.CharField(
        max_length=20,
        choices=Activity.TASK_PRIORITY_CHOICES,
        null=True,
        blank=True,
        verbose_name=_("Priority"),
    )
    task_owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cadence_task_followups",
        verbose_name=_("Task Owner"),
    )

    # Call
    call_type = models.CharField(
        max_length=20, default="outbound", verbose_name=_("Call Type")
    )
    call_status = models.CharField(
        max_length=20, default="scheduled", verbose_name=_("Call Status")
    )
    call_start_after_days = models.PositiveIntegerField(
        null=True, blank=True, verbose_name=_("Call Start + Days")
    )
    call_owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cadence_call_followups",
        verbose_name=_("Call Owner"),
    )
    purpose = models.CharField(
        max_length=255, null=True, blank=True, verbose_name=_("Purpose")
    )

    # Email
    to = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Mail To"),
        help_text=_(
            "Recipients for this step. Choose user/email fields from the record"
        ),
    )
    email_template = models.ForeignKey(
        HorillaMailTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cadence_followups",
        verbose_name=_("Mail Template"),
    )

    class Meta:
        """Meta class for CadenceFollowUp"""

        verbose_name = _("Cadence Follow Up")
        verbose_name_plural = _("Cadence Follow Ups")
        ordering = ["followup_number", "order", "created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["cadence"],
                condition=Q(followup_number=1),
                name="unique_first_followup_per_cadence",
            ),
            models.UniqueConstraint(
                fields=["cadence", "followup_number", "previous_status"],
                condition=Q(followup_number__gt=1)
                & Q(previous_status__isnull=False)
                & Q(branch_from__isnull=True),
                name="unique_previous_status_per_followup_bucket_unbranched",
            ),
            models.UniqueConstraint(
                fields=["cadence", "followup_number", "branch_from", "previous_status"],
                condition=Q(followup_number__gt=1)
                & Q(previous_status__isnull=False)
                & Q(branch_from__isnull=False),
                name="unique_previous_status_per_followup_bucket_branch",
            ),
        ]

    def __str__(self):
        return f"{self.cadence} - {self.get_followup_type_display()} ({self.followup_number})"

    def get_edit_url(self):
        """Return the URL for editing this follow-up."""
        return reverse_lazy(
            "cadences:cadence_followup_update_view", kwargs={"pk": self.pk}
        )

    def get_delete_url(self):
        """Return the URL for deleting this follow-up (UI hides when branch children exist)."""
        return reverse_lazy(
            "cadences:cadence_followup_delete_view", kwargs={"pk": self.pk}
        )

    TYPE_REQUIRED_FIELDS = {
        "task": (
            "subject",
            "due_after_days",
            "task_status",
            "task_priority",
            "task_owner",
        ),
        "call": ("call_start_after_days", "call_owner", "purpose"),
        "email": ("to", "email_template"),
    }

    def _validate_followup_number(self, errors):
        if self.followup_number == 1 and self.cadence_id:
            if (
                CadenceFollowUp.objects.filter(
                    cadence_id=self.cadence_id, followup_number=1
                )
                .exclude(pk=self.pk)
                .exists()
            ):
                errors["followup_number"] = _("Follow up 1 can only contain one item.")
            self.previous_status = None
        else:
            if not self.previous_status:
                errors["previous_status"] = _(
                    "Select status condition from previous follow-up."
                )
            if (
                self.cadence_id
                and not CadenceFollowUp.objects.filter(
                    cadence_id=self.cadence_id, followup_number=self.followup_number - 1
                ).exists()
            ):
                errors["followup_number"] = _(
                    "Cannot add this follow-up before creating previous follow-up bucket."
                )

    def _validate_do_this(self, errors):
        if self.do_this_unit == "immediately":
            self.do_this_value = None
        elif not self.do_this_value:
            errors["do_this_value"] = _("Enter value for selected Do This unit.")

    def _validate_type_required_fields(self, errors):
        if self.followup_type == "call":
            self.call_type = "outbound"
            self.call_status = "scheduled"

        required_fields = self.TYPE_REQUIRED_FIELDS.get(self.followup_type, ())
        msg = _("This field is required for selected follow-up type.")
        for field_name in required_fields:
            if getattr(self, field_name, None) in (None, ""):
                errors[field_name] = msg

    def clean(self):
        """Validate follow-up type, number, timing, and type-specific required fields."""
        super().clean()
        errors = {}

        valid_types = {choice[0] for choice in self.FOLLOWUP_TYPE_CHOICES}
        if self.followup_type not in valid_types:
            raise ValidationError({"followup_type": _("Invalid follow-up type.")})

        self._validate_followup_number(errors)
        self._validate_do_this(errors)
        self._validate_type_required_fields(errors)

        if errors:
            raise ValidationError(errors)
