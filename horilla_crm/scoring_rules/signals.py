"""
Signal handlers for the scoring_rules app.
Recalculates scores for all affected modules when scoring rules, criteria, or conditions change.
"""

# Standard library imports
import logging

# Third-party imports (Django)
from django.conf import settings
from django.dispatch import receiver

from horilla.apps import apps
from horilla.core.exceptions import FieldDoesNotExist

# First party imports (Horilla)
from horilla.db import transaction
from horilla.db.models import Case, F, IntegerField, Q, When
from horilla.db.models.signals import post_save, pre_delete

# Local imports
from horilla_crm.scoring_rules.models import (
    ScoringCondition,
    ScoringCriterion,
    ScoringRule,
)

try:
    from horilla_crm.scoring_rules.tasks import recalculate_scores_for_module_task

    CELERY_AVAILABLE = True
except Exception as e:
    logger = logging.getLogger(__name__)
    logger.warning(
        "Celery tasks not available, will use synchronous execution: %s", str(e)
    )
    CELERY_AVAILABLE = False
    recalculate_scores_for_module_task = None

if "logger" not in locals():
    logger = logging.getLogger(__name__)


def get_score_field(model):
    """Get the score field name for a given model."""
    score_fields = {
        "lead": "lead_score",
        "opportunity": "opportunity_score",
        "account": "account_score",
        "contact": "contact_score",
    }
    return score_fields.get(model._meta.model_name)


def get_models_for_module(module):
    """
    Dynamically find models matching a module name (e.g., 'lead') across installed apps.
    Only includes models that have a corresponding score field.
    """
    models = []
    for app_config in apps.get_app_configs():
        for model in app_config.get_models():
            if model._meta.model_name == module:
                score_field = get_score_field(model)
                if score_field and score_field in [f.name for f in model._meta.fields]:
                    models.append(model)
    return models


def build_query_from_conditions(criterion, Model):
    """
    Build a Django ORM query to filter instances that match a criterion's conditions.

    Args:
        criterion: ScoringCriterion instance.
        Model: The Django model class (e.g., Lead).

    Returns:
        Q object representing the combined conditions.
    """
    query = Q()
    for condition in criterion.conditions.all().order_by("order"):
        field = condition.field
        operator = condition.operator
        value = condition.value
        logical_operator = condition.logical_operator

        try:
            Model._meta.get_field(field)
            if operator == "equals":
                if Model._meta.get_field(field).get_internal_type() == "ForeignKey":
                    condition_query = Q(**{f"{field}_id__exact": value})
                else:
                    condition_query = Q(**{f"{field}__exact": value})
            elif operator == "not_equals":
                if Model._meta.get_field(field).get_internal_type() == "ForeignKey":
                    condition_query = ~Q(**{f"{field}_id__exact": value})
                else:
                    condition_query = ~Q(**{f"{field}__exact": value})
            elif operator == "contains":
                condition_query = Q(**{f"{field}__icontains": value})
            elif operator == "not_contains":
                condition_query = ~Q(**{f"{field}__icontains": value})
            elif operator == "starts_with":
                condition_query = Q(**{f"{field}__istartswith": value})
            elif operator == "ends_with":
                condition_query = Q(**{f"{field}__iendswith": value})
            elif operator == "greater_than":
                try:
                    condition_query = Q(**{f"{field}__gt": float(value)})
                except (ValueError, TypeError):
                    condition_query = Q(pk__in=[])
            elif operator == "greater_than_equal":
                try:
                    condition_query = Q(**{f"{field}__gte": float(value)})
                except (ValueError, TypeError):
                    condition_query = Q(pk__in=[])
            elif operator == "less_than":
                try:
                    condition_query = Q(**{f"{field}__lt": float(value)})
                except (ValueError, TypeError):
                    condition_query = Q(pk__in=[])
            elif operator == "less_than_equal":
                try:
                    condition_query = Q(**{f"{field}__lte": float(value)})
                except (ValueError, TypeError):
                    condition_query = Q(pk__in=[])
            elif operator == "is_empty":
                condition_query = Q(**{field: None}) | Q(**{f"{field}__exact": ""})
            elif operator == "is_not_empty":
                condition_query = ~Q(**{field: None}) & ~Q(**{f"{field}__exact": ""})
            else:
                condition_query = Q(pk__in=[])

            if logical_operator == "and":
                query &= condition_query
            else:
                query |= condition_query
        except FieldDoesNotExist:
            logger.warning(
                "Field %s does not exist on %s", field, Model._meta.model_name
            )
            query &= Q(pk__in=[])

    return query


def update_all_scores_for_module(module):
    """
    Update score fields for instances matching active scoring rules' conditions
    using direct database UPDATE queries.

    Args:
        module: String (e.g., 'lead', 'opportunity') indicating the module.
    """
    models = get_models_for_module(module)
    for Model in models:
        score_field = get_score_field(Model)
        if not score_field:
            continue

        with transaction.atomic():
            try:
                Model.objects.update(**{score_field: 0})
                logger.info(
                    "Reset %s to 0 for all %s instances",
                    score_field,
                    Model._meta.model_name,
                )
            except Exception as e:
                logger.error(
                    "Error resetting %s for %s: %s",
                    score_field,
                    Model._meta.model_name,
                    e,
                )
                raise

            rules = ScoringRule.objects.filter(module__model=module, is_active=True)
            if not rules.exists():
                continue

            for rule in rules:
                for criterion in rule.criteria.all().order_by("order"):
                    query = build_query_from_conditions(criterion, Model)
                    if not query:
                        continue

                    points = criterion.points
                    if criterion.operation_type == "sub":
                        points = -points

                    try:
                        Model.objects.filter(query).update(
                            **{
                                score_field: Case(
                                    When(query, then=F(score_field) + points),
                                    default=F(score_field),
                                    output_field=IntegerField(),
                                )
                            }
                        )
                        logger.info(
                            "Updated %s for %s instances matching criterion %s",
                            score_field,
                            Model._meta.model_name,
                            criterion.id,
                        )
                    except Exception as e:
                        logger.error(
                            "Error updating %s for %s with criterion %s: %s",
                            score_field,
                            Model._meta.model_name,
                            criterion.id,
                            e,
                        )
                        raise


def dispatch_recalculation(module):
    """
    Recalculate scores for a module, offloading to Celery when available so
    that saving/deleting a scoring rule doesn't block the request/response
    cycle on a full-table rescore.
    """
    use_async = getattr(settings, "USE_ASYNC_SCORING", False)

    if use_async and CELERY_AVAILABLE and recalculate_scores_for_module_task:
        try:
            transaction.on_commit(
                lambda: recalculate_scores_for_module_task.delay(module)
            )
            return
        except Exception as celery_error:
            logger.warning(
                "Failed to queue scoring recalculation task, falling back to sync: %s",
                celery_error,
            )

    update_all_scores_for_module(module)


@receiver(post_save, sender=ScoringRule)
@receiver(pre_delete, sender=ScoringRule)
def handle_rule_change(sender, instance, **kwargs):
    """Recalculate all scores for the associated module when a scoring rule changes."""
    dispatch_recalculation(instance.module.model)


@receiver(post_save, sender=ScoringCriterion)
@receiver(pre_delete, sender=ScoringCriterion)
def handle_criterion_change(sender, instance, **kwargs):
    """Recalculate all scores when a scoring criterion changes."""
    dispatch_recalculation(instance.rule.module.model)


@receiver(post_save, sender=ScoringCondition)
@receiver(pre_delete, sender=ScoringCondition)
def handle_condition_change(sender, instance, **kwargs):
    """Recalculate all scores when a scoring condition changes."""
    dispatch_recalculation(instance.criterion.rule.module.model)
