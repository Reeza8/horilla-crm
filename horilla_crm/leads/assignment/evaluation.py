"""
Evaluate lead assignment-rule criteria against plain data.

``compare`` and ``normalise`` hold the operator semantics used by both the
post-save engine (``horilla_crm.leads.signals``) and the lead forms, so a
criterion means exactly the same thing on both paths.

The form path works on a form's ``cleaned_data`` and has three outcomes per
criterion (``Match``): ``YES``, ``NO`` and ``UNKNOWN``. ``UNKNOWN`` means the
value is not available yet, e.g. a later step of the multi-step form has not
been filled in, so the preview can not decide.
"""

# Standard library imports
import logging
from enum import Enum

# First party imports (Horilla)
from horilla.core.exceptions import FieldDoesNotExist
from horilla.utils.translation import gettext_lazy as _

logger = logging.getLogger(__name__)


class Match(Enum):
    """Result of evaluating a criterion or a whole condition."""

    YES = "yes"
    NO = "no"
    UNKNOWN = "unknown"


def normalise(value):
    """
    Turn a Python value from a form into the string the engine compares.

    * ``None`` becomes an empty string.
    * A related object (foreign key) becomes its primary key, as the engine
      compares foreign keys by pk.
    * A list/tuple/queryset (multi-select custom fields) becomes a
      comma-separated string, the same way custom field values are read back.
    * Anything else becomes ``str(value)``.
    """
    if value is None:
        return ""
    if hasattr(value, "pk"):
        return str(value.pk)
    if isinstance(value, (list, tuple, set, frozenset)) or hasattr(value, "all"):
        items = value.all() if hasattr(value, "all") else value
        return ",".join(normalise(item) for item in items)
    return str(value)


def compare(operator, actual, expected, field=""):
    """
    Apply ``operator`` to the lead's value (``actual``) and the criterion's
    value (``expected``). Both are strings. Returns ``True`` on a match.

    This is the single implementation of the operator semantics; the engine
    and the forms both call it.
    """
    actual = "" if actual is None else actual
    expected = expected or ""
    try:
        if operator == "exact":
            return actual == expected
        if operator == "ne":
            return actual != expected
        if operator == "icontains":
            return expected.lower() in actual.lower()
        if operator == "not_contains":
            return expected.lower() not in actual.lower()
        if operator == "istartswith":
            return actual.lower().startswith(expected.lower())
        if operator == "iendswith":
            return actual.lower().endswith(expected.lower())
        if operator == "isnull":
            return not actual.strip()
        if operator == "isnotnull":
            return bool(actual.strip())
        if operator in ("gt", "gte", "lt", "lte"):
            try:
                fv, rv = float(actual), float(expected)
                return {"gt": fv > rv, "gte": fv >= rv, "lt": fv < rv, "lte": fv <= rv}[
                    operator
                ]
            except (ValueError, TypeError):
                return False
        if operator == "between":
            parts = [p.strip() for p in expected.split(",") if p.strip()]
            if len(parts) == 2:
                try:
                    fv = float(actual)
                    return float(parts[0]) <= fv <= float(parts[1])
                except (ValueError, TypeError):
                    return False
    except Exception as exc:
        logger.error("Assignment rule criterion eval error (field=%s): %s", field, exc)

    return False


def _field_is_known(field):
    """Return True if ``field`` is a Lead field or a registered condition field."""
    # First party imports (Horilla)
    from horilla.contrib.generics.forms.condition_fields import (
        get_condition_field_extension,
    )

    # Local imports
    from horilla_crm.leads.models import Lead

    if get_condition_field_extension(field) is not None:
        return True
    try:
        Lead._meta.get_field(field)
    except FieldDoesNotExist:
        return False
    return True


def criterion_result(criteria, data, *, final):
    """
    Evaluate one ``LeadAssignmentMatchCriteria`` row against ``data``.

    ``data`` maps a field name (a Lead field, or ``cf_<pk>`` for a custom
    field) to a Python value, normally a form's ``cleaned_data``.

    When the field is not in ``data``: with ``final=False`` the result is
    ``UNKNOWN``; with ``final=True`` the value is treated as empty, which is
    what a saved lead would have.
    """
    field = criteria.field
    if field in data:
        actual = normalise(data[field])
    elif not final:
        return Match.UNKNOWN
    elif not _field_is_known(field):
        logger.warning("Assignment rule: field '%s' does not exist on Lead", field)
        return Match.NO
    else:
        actual = ""

    matched = compare(criteria.operator, actual, criteria.value or "", field=field)
    return Match.YES if matched else Match.NO


def _join(operator, left, right):
    """Combine two results with AND/OR, where ``UNKNOWN`` only decides when it can."""
    if operator == "or":
        if Match.YES in (left, right):
            return Match.YES
        if Match.UNKNOWN in (left, right):
            return Match.UNKNOWN
        return Match.NO
    if Match.NO in (left, right):
        return Match.NO
    if Match.UNKNOWN in (left, right):
        return Match.UNKNOWN
    return Match.YES


def _criteria_results(condition, data, final):
    """Return ``[(criteria, Match), ...]`` in the engine's evaluation order."""
    return [
        (criteria, criterion_result(criteria, data, final=final))
        for criteria in condition.criteria.all()
    ]


def condition_result(condition, data, *, final):
    """
    Evaluate every criterion of a condition with its AND/OR logic.

    The rows are folded left to right; each row's ``logical_operator`` joins it
    to what came before, exactly as the engine does. A condition with no
    criteria always matches.
    """
    results = _criteria_results(condition, data, final)
    if not results:
        return Match.YES

    outcome = None
    for criteria, row in results:
        if outcome is None:
            outcome = row
        else:
            outcome = _join(criteria.logical_operator, outcome, row)
    return outcome


# What a failed criterion means for the lead, in plain words.
_FAILURE_TEXT = {
    "exact": _("%(field)s is not %(value)s"),
    "ne": _("%(field)s is %(value)s"),
    "icontains": _("%(field)s does not contain %(value)s"),
    "not_contains": _("%(field)s contains %(value)s"),
    "istartswith": _("%(field)s does not start with %(value)s"),
    "iendswith": _("%(field)s does not end with %(value)s"),
    "gt": _("%(field)s is not greater than %(value)s"),
    "gte": _("%(field)s is not greater than or equal to %(value)s"),
    "lt": _("%(field)s is not less than %(value)s"),
    "lte": _("%(field)s is not less than or equal to %(value)s"),
    "isnull": _("%(field)s is not empty"),
    "isnotnull": _("%(field)s is empty"),
    "between": _("%(field)s is not between %(value)s"),
}


def _display_value(criteria):
    """Human readable value of a criterion (foreign keys and choices resolved)."""
    value = criteria.get_display_value()
    # Local imports
    from horilla_crm.leads.models import Lead

    try:
        choices = dict(Lead._meta.get_field(criteria.field).flatchoices)
    except (FieldDoesNotExist, AttributeError):
        return value
    return str(choices.get(criteria.value, value))


def explain_failure(condition, data, *, final):
    """
    Describe why ``condition`` does not match, e.g. ``"Lead Source is not Website"``.

    Only the criteria that did not match are listed, joined with ", ".
    """
    reasons = []
    for criteria, row in _criteria_results(condition, data, final):
        if row is not Match.NO:
            continue
        template = _FAILURE_TEXT.get(criteria.operator)
        if template is None:
            continue
        reasons.append(
            str(template)
            % {
                "field": str(criteria.get_field_label()),
                "value": _display_value(criteria),
            }
        )
    return ", ".join(reasons)
