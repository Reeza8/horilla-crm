# Scoring Rules (`horilla_crm.scoring_rules.views.scoring_rule`)

## What this module does

Manages **ScoringRule** records — rules that accumulate point scores on leads based on field-match criteria. Each rule has child `ScoringCriterion` rows; each criterion has `ScoringCondition` rows.

---

## View inventory

| View | Base | Purpose |
|------|------|---------|
| `ScoringRuleView` | `HorillaView` | Main shell template |
| `ScoringRuleNavbar` | `HorillaNavView` | Navigation bar with "Create Rule" action |
| `ScoringRuleListView` | `HorillaListView` | Rule list with edit/delete/activate column actions |
| `ScoringRuleFormView` | `HorillaSingleFormView` | Create/update a scoring rule |
| `ScoringRuleDeleteView` | `HorillaSingleDeleteView` | Delete a scoring rule |
| `ScoringRuleDetailView` | `HorillaDetailView` | Rule detail page showing criteria list |
| `ScoringRuleDetailNavbar` | `HorillaNavView` | Navbar for the detail page |
| `ScoringCriterionCreateUpdateView` | `HorillaSingleFormView` | Create/update a criterion linked to a rule |
| `ScoringCriteriaDeleteView` | `HorillaSingleDeleteView` | Delete a criterion |
| `ScoringActiveToggleView` | `View` | HTMX POST — toggles `is_active` on a rule |

---

## Key patterns

### Dynamic `model_name` in criterion form

`ScoringCriterionCreateUpdateView` resolves the target model for field choices in two ways:

1. **From parent rule**: if `obj` (rule PK) is in GET params, the criterion form reads the rule's `model_name` and injects it as initial.
2. **From GET param directly**: `?model_name=leads.Lead` is accepted for cases where the rule context is already known.

Invalid `obj_id` or `model_name` values are caught and logged (no unhandled exception).

### Score computation (`scoring_rules/utils.py`)

`compute_score()` evaluates matching criteria for a record. Criteria and their
conditions are **prefetched** so a save does O(1) query shape for the rule
tree instead of N+1 per criterion/condition.

### URL param cleanup

Some HTMX call chains append extra query strings, producing values like `3?obj=3`. The view normalizes `obj` via:

```python
obj = request.GET.get("obj", "").split("?")[0].strip()
```

This prevents `DoesNotExist` errors from malformed URLs without requiring callers to be perfectly clean.

### `@cached_property form_url` with preserved query params

`ScoringCriterionCreateUpdateView.form_url` preserves `obj` and `model_name` query params in the submission URL so the form reloads with the correct context if re-rendered after validation errors.

### Active toggle

`ScoringActiveToggleView` is a simple `View` that flips `is_active` on the rule, saves, and returns an HTMX response triggering a list row update — no full page reload needed.

---

## Scoring rule signals

Three Django signal receivers in `scoring_rules/signals.py` recalculate lead scores when rules, criteria, or conditions change:

- `post_save` on `ScoringRule` → recalculates scores for all affected leads.
- `post_save` on `ScoringCriterion` → same.
- `post_save` / `post_delete` on `ScoringCondition` → same.

These are auto-imported by `AppLauncher` via `auto_import_modules = ["signals"]`.

---

## URL names (reference)

All URLs are namespaced under `scoring_rules:`.

| Name | View |
|------|------|
| `scoring_rules:scoring_rule_view` | `ScoringRuleView` |
| `scoring_rules:scoring_rule_list` | `ScoringRuleListView` |
| `scoring_rules:scoring_rule_form` | `ScoringRuleFormView` (create) |
| `scoring_rules:scoring_rule_form` with `pk` | `ScoringRuleFormView` (update) |
| `scoring_rules:scoring_rule_delete` | `ScoringRuleDeleteView` |
| `scoring_rules:scoring_rule_detail` | `ScoringRuleDetailView` |
| `scoring_rules:scoring_criterion_form` | `ScoringCriterionCreateUpdateView` |
| `scoring_rules:scoring_criterion_delete` | `ScoringCriteriaDeleteView` |
| `scoring_rules:scoring_active_toggle` | `ScoringActiveToggleView` |

---

## Related documentation

- Lead scoring pipeline: [../leads/assignment_rule.md](../leads/assignment_rule.md)
- `HorillaSingleFormView`: [../../horilla/contrib/generics/views/single_form.md](../../horilla/contrib/generics/views/single_form.md)
- Signals auto-import: [../../horilla/contrib/core/core_app.md](../../horilla/contrib/core/core_app.md)
