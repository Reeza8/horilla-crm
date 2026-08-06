# Condition widget helpers (`horilla_generics/views/helpers/condition_widget.py`)

## Purpose

This module provides HTMX helper endpoints for condition/filter builders:

1. removing a condition row,
2. rendering the correct **value input widget** based on selected field type,
3. updating operator dropdown options by field type (OOB swap),
4. returning model field choices for dynamic field selectors.

It is used by generic single-form condition rows, automation/rule UIs, dashboard condition builders, and forecast condition sections.

---

## Views in this module

## 1) `RemoveConditionRowView`

```python
class RemoveConditionRowView(LoginRequiredMixin, View):
```

- HTMX-only (`@htmx_required`)
- method: `DELETE`
- endpoint: `horilla_generics:remove_condition_row`
- behavior: returns empty `HttpResponse("")` (200), so front-end can remove the row element.

Typical template usage:

```html
<button hx-delete="/generics/remove-condition-row/{{ row_id }}/" ...>
```

---

## 2) `GetFieldValueWidgetView`

```python
class GetFieldValueWidgetView(LoginRequiredMixin, View):
```

Main endpoint for dynamic value-input rendering after field/operator changes.

### Input parameters

Common GET params:

- `row_id`
- `field_<row_id>` or `field`
- `operator_<row_id>` (or fallback)
- `value_<row_id>` / `value_start_<row_id>` / `value_end_<row_id>`
- `model_name` (or inferred via content type `model`)
- `condition_model` (used to decide whether to emit operator OOB swap)

### Model resolution behavior

If `model_name` is missing, it tries:

- `model` query param as content type id (`HorillaContentType`)
- resolves `ct.model`

### Output behavior

1. Builds value widget HTML via `_get_value_widget_html(...)`.
2. For single-form condition rows, optionally builds out-of-band operator select HTML via `_get_operator_oob_html(...)`.
3. Concatenates both and renders through Django template engine (`Template("{{ widget_html }}")`) before returning response.

---

## Operator OOB update (`_get_operator_oob_html`)

When `condition_model` and `row_id` are present, this method:

1. resolves model + selected field,
2. maps field to normalized field type (`_get_field_type_for_condition`),
3. pulls operator choices from `OPERATOR_CHOICES`,
4. returns an OOB wrapper:
   - container id: `id_operator_<row_id>_container`
   - `hx-swap-oob="true"`
   - `<select name="operator_<row_id>">...`
5. wires select change to call `get_field_value_widget` again with proper `hx-include`.

This keeps operator/value widgets in sync (e.g., changing to `between` swaps to two inputs).

---

## Value widget rendering rules (`_get_value_widget_html`)

If field/model cannot be resolved -> fallback text input.

Resolved field-type mapping:

- `ManyToManyField` -> multi-select (`_render_multiselect_input`)
- `ForeignKey` -> select options from related model (`_render_select_input`)
- choice fields -> select (`_render_select_input`)
- boolean -> boolean select (`True/False`)
- date -> date input
- datetime -> datetime-local input
- time -> time input
- integer/decimal -> number input (`step=0.01` for decimal)
- email/url/text -> specialized input/textarea
- default -> text input

### Special `between` handling

If operator is `between`:

- `DateField` -> two date inputs (`value_start_*`, `value_end_*`)
- `DateTimeField` -> two datetime-local inputs

The widget is rendered side-by-side in one container.

---

## 3) `GetModelFieldChoicesView`

```python
class GetModelFieldChoicesView(LoginRequiredMixin, View):
```

Endpoint for returning selectable model fields (usually for "field" dropdown in condition rows).

Route: `horilla_generics:get_model_field_choices`

### Input params

- `content_type` or `model` (content type id)
- `row_id`
- optional `field_name_pattern` (default `field_{row_id}`)
- optional filters:
  - `field_types=CharField,DateField,...`
  - `exclude_fields=a,b,c`
  - `exclude_choice_fields=true|false`
  - `only_text_fields=true|false`

### Selection logic

- resolves model via `HorillaContentType` -> model name -> app registry lookup
- iterates only forward model fields (`_meta.fields + _meta.many_to_many`)
- excludes defaults (`id`, audit fields, company, etc.) + custom excludes
- skips non-editable fields
- applies type and choice filters
- builds field choices list beginning with blank option

Returns rendered partial:

- `partials/field_select_empty.html`

---

## Where it is used

Referenced by:

- `single_form_view.html`
- `partials/condition_row.html`
- dashboard/forecast condition templates
- `single_form_builder` helper internals
- generic URLs:
  - `/generics/remove-condition-row/<row_id>/`
  - `/generics/get-field-value-widget/`
  - `/generics/get-model-field-choices/`

---

## Example 1: field change -> value widget refresh

```html
<select
  name="field_0"
  hx-get="{% url 'horilla_generics:get_field_value_widget' %}"
  hx-target="#id_value_0_container"
  hx-swap="innerHTML"
  hx-vals='{"row_id":"0","model_name":"lead","condition_model":"leads.scoringrule"}'
  hx-include='[name="field_0"],[name="operator_0"],[name="value_0"]'>
</select>
```

Result:

- backend returns suitable input widget for selected field type,
- may also return OOB operator select update.

---

## Example 2: operator change (`between`)

When operator changes to `between`, request includes:

```text
row_id=0
field_0=close_date
operator_0=between
model_name=opportunity
```

Response widget becomes:

- `value_start_0` + `value_end_0` date/datetime pair.

---

## Example 3: populate field dropdown from content type

```html
<select
  name="model"
  hx-get="{% url 'horilla_generics:get_model_field_choices' %}"
  hx-target="#field-row-0-container"
  hx-vals='{"row_id":"0","exclude_choice_fields":"true"}'
  hx-swap="innerHTML">
  ...
</select>
```

Backend resolves selected content type and returns allowed field options.

---

## Notes

- HTML is built with Horilla HTML helpers from `horilla.utils.html` (`format_html`, `format_html_join`, `escape`) to reduce XSS risk.
- Many model-resolution paths iterate installed apps to locate model by name; this favors flexibility but requires unique model naming expectations.
- OOB operator replacement is intentionally limited to condition-model flows so generic filter behavior remains predictable.

---

## Summary

`condition_widget.py` is the dynamic glue for condition-row UX: it adapts both field options and value/operator widgets in real time based on selected model field type, while keeping responses HTMX-friendly and reusable across many forms.
