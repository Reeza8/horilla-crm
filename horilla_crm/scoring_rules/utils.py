"""Utility functions for the scoring_rules module."""

from horilla.db.models import Prefetch
from horilla_crm.scoring_rules.models import (
    ScoringCondition,
    ScoringCriterion,
    ScoringRule,
)


def compute_score(instance):
    """
    Compute the score for a given instance (Lead, Opportunity, Account, or Contact)
    based on active ScoringRules for the instance's module.

    Args:
        instance: A model instance (e.g., Lead, Opportunity) to score.

    Returns:
        int: The computed score (sum of points from matching criteria).
    """
    model_name = instance._meta.model_name
    rules = ScoringRule.objects.filter(
        module__model=model_name, is_active=True
    ).prefetch_related(
        Prefetch(
            "criteria",
            queryset=ScoringCriterion.objects.order_by("order").prefetch_related(
                Prefetch(
                    "conditions",
                    queryset=ScoringCondition.objects.order_by("order"),
                )
            ),
        )
    )
    score = 0

    for rule in rules:
        for criterion in rule.criteria.all():
            if criterion.evaluate_conditions(instance):
                points = criterion.points
                if criterion.operation_type == "sub":
                    points = -points
                score += points

    return score
