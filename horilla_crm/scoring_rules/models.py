"""
Scoring rule and criterion models for lead/opportunity/account/contact scoring.
"""

# Standard library imports
import logging

# Third-party imports (Django)
from django.utils.dateparse import parse_date, parse_datetime

from horilla.contrib.core.models import HorillaContentType, HorillaCoreModel
from horilla.contrib.utils.methods import render_template

# First-party / Horilla imports
from horilla.db import models
from horilla.registry.limiters import limit_content_types
from horilla.registry.permission_registry import permission_exempt_model
from horilla.urls import reverse_lazy
from horilla.utils.choices import OPERATOR_CHOICES
from horilla.utils.translation import gettext_lazy as _

logger = logging.getLogger(__name__)


class ScoringRule(HorillaCoreModel):
    """Scoring rule for calculating lead/opportunity/account/contact scores."""

    name = models.CharField(max_length=100, verbose_name=_("Rule Name"))
    module = models.ForeignKey(
        HorillaContentType,
        on_delete=models.PROTECT,
        verbose_name=_("Module"),
        limit_choices_to=limit_content_types("scoring_models"),
    )
    description = models.TextField(blank=True, null=True, verbose_name=_("Description"))

    def __str__(self):
        return str(self.name)

    def is_active_col(self):
        """Return HTML for active status column."""
        html = render_template(
            path="components/toggle_active_col.html",
            context={
                "instance": self,
                "toggle_url": reverse_lazy(
                    "scoring_rules:scoring_rule_activate", kwargs={"pk": self.pk}
                ),
            },
        )
        return html

    def get_edit_url(self):
        """Return the edit URL for this scoring rule."""
        return reverse_lazy(
            "scoring_rules:scoring_rule_update_form", kwargs={"pk": self.pk}
        )

    def get_delete_url(self):
        """Return the delete URL for this scoring rule."""
        return reverse_lazy(
            "scoring_rules:scoring_rule_delete_view", kwargs={"pk": self.pk}
        )

    def get_detail_view_url(self):
        """Return the detail view URL for this scoring rule."""
        return reverse_lazy(
            "scoring_rules:scoring_rule_detail_view", kwargs={"pk": self.pk}
        )

    class Meta:
        """Meta options for the Scoring Rule model."""

        verbose_name = _("Scoring Rule")
        verbose_name_plural = _("Scoring Rules")


class ScoringCriterion(HorillaCoreModel):
    """Main scoring criterion that contains multiple conditions"""

    rule = models.ForeignKey(
        ScoringRule, on_delete=models.CASCADE, related_name="criteria"
    )
    name = models.CharField(
        max_length=200, blank=True, verbose_name=_("Criterion Name")
    )
    points = models.IntegerField(verbose_name=_("Points to Award"))
    operation_type = models.CharField(
        max_length=3,
        choices=[("add", _("Add")), ("sub", _("Sub"))],
        default="and",
        verbose_name=_("Operation Type"),
    )
    order = models.PositiveIntegerField(default=0, verbose_name=_("Order"))

    def __str__(self):
        return f"{self.rule.name} - {self.name or f'Criterion {self.pk}'}"

    def evaluate_conditions(self, instance):
        """
        Evaluate all conditions for this criterion against the given instance.
        Returns True if all conditions are met according to their logical operators.
        """
        conditions = self.conditions.all().order_by("order")
        if not conditions.exists():
            return False

        result = None
        for condition in conditions:
            condition_result = condition.evaluate(instance)
            if result is None:
                result = condition_result
            else:
                if condition.logical_operator == "and":
                    result = result and condition_result
                else:
                    result = result or condition_result

        return result

    class Meta:
        """Meta options for ScoringCriterion."""

        verbose_name = _("Scoring Criterion")
        verbose_name_plural = _("Scoring Criteria")
        ordering = ["order", "id"]


@permission_exempt_model
class ScoringCondition(HorillaCoreModel):
    """Individual conditions within a scoring criterion"""

    criterion = models.ForeignKey(
        ScoringCriterion, on_delete=models.CASCADE, related_name="conditions"
    )
    field = models.CharField(max_length=100, verbose_name=_("Field Name"))
    operator = models.CharField(
        max_length=50,
        choices=OPERATOR_CHOICES,
        verbose_name=_("Operator"),
    )
    value = models.CharField(max_length=255, blank=True, verbose_name=_("Value"))
    logical_operator = models.CharField(
        max_length=3,
        choices=[("and", _("AND")), ("or", _("OR"))],
        default="and",
        verbose_name=_("Logical Operator"),
    )
    order = models.PositiveIntegerField(default=0, verbose_name=_("Order"))

    def __str__(self):
        return f"{self.field} {self.operator} {self.value}"

    def evaluate(self, instance):
        """
        Evaluate this condition against the given instance.
        Returns True if the condition is met, False otherwise.
        """
        try:
            field = instance._meta.get_field(self.field)
            raw_value = getattr(instance, self.field, None)
            field_type = getattr(field, "get_internal_type", lambda: "")()
            is_date_field = field_type == "DateField"
            is_datetime_field = field_type == "DateTimeField"
            value = self.value or ""
            op = self.operator

            if is_date_field or is_datetime_field:
                if op in ("isnull", "is_empty"):
                    return raw_value is None
                if op in ("isnotnull", "is_not_empty"):
                    return raw_value is not None
                if op in ("exact", "equals", "gt", "lt", "between"):
                    if op == "exact":
                        op = "equals"
                    if op == "equals":
                        comp = (
                            parse_date(value)
                            if is_date_field
                            else parse_datetime(value)
                        )
                        if comp is None:
                            return str(raw_value) == value
                        return raw_value is not None and raw_value == comp
                    if op == "gt":
                        comp = (
                            parse_date(value)
                            if is_date_field
                            else parse_datetime(value)
                        )
                        return (
                            comp is not None
                            and raw_value is not None
                            and raw_value > comp
                        )
                    if op == "lt":
                        comp = (
                            parse_date(value)
                            if is_date_field
                            else parse_datetime(value)
                        )
                        return (
                            comp is not None
                            and raw_value is not None
                            and raw_value < comp
                        )
                    if op == "between":
                        parts = [p.strip() for p in value.split(",", 1) if p.strip()]
                        if len(parts) >= 2:
                            start_val = (
                                parse_date(parts[0])
                                if is_date_field
                                else parse_datetime(parts[0])
                            )
                            end_val = (
                                parse_date(parts[1])
                                if is_date_field
                                else parse_datetime(parts[1])
                            )
                            if start_val and end_val and raw_value is not None:
                                return start_val <= raw_value <= end_val
                        return False

            if op == "exact":
                op = "equals"
            if op == "gt":
                op = "greater_than"
            if op == "lt":
                op = "less_than"
            if op == "isnull":
                op = "is_empty"
            if op == "isnotnull":
                op = "is_not_empty"

            field_value = "" if raw_value is None else str(raw_value)

            if op == "equals":
                return field_value == value
            if op == "not_equals":
                return field_value != value
            if op == "contains":
                return value.lower() in field_value.lower()
            if op == "not_contains":
                return value.lower() not in field_value.lower()
            if op == "starts_with":
                return field_value.lower().startswith(value.lower())
            if op == "ends_with":
                return field_value.lower().endswith(value.lower())
            if op == "greater_than":
                try:
                    return float(field_value) > float(value)
                except (ValueError, TypeError):
                    return False
            if op == "greater_than_equal":
                try:
                    return float(field_value) >= float(value)
                except (ValueError, TypeError):
                    return False
            if op == "less_than":
                try:
                    return float(field_value) < float(value)
                except (ValueError, TypeError):
                    return False
            if op == "less_than_equal":
                try:
                    return float(field_value) <= float(value)
                except (ValueError, TypeError):
                    return False
            if op == "is_empty":
                return not field_value or field_value.strip() == ""
            if op == "is_not_empty":
                return bool(field_value and field_value.strip())

            return False

        except Exception as e:
            logger.error("Error evaluating condition %s: %s", self, e)
            return False

    class Meta:
        """Meta options for ScoringCondition."""

        verbose_name = _("Scoring Condition")
        verbose_name_plural = _("Scoring Conditions")
        ordering = ["order", "id"]


@permission_exempt_model
class EmailActivityScoring(HorillaCoreModel):
    """Email activity scoring configuration."""

    rule = models.ForeignKey(
        ScoringRule, on_delete=models.CASCADE, related_name="email_activities"
    )
    activity_type = models.CharField(
        max_length=50,
        choices=[
            ("opened", _("Opened")),
            ("clicked", _("Clicked")),
            ("bounced", _("Bounced")),
        ],
    )
    points = models.IntegerField(default=10)

    def __str__(self):
        return f"{self.activity_type} - {self.points} points"
