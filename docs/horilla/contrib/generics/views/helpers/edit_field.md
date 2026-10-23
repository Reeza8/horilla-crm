# Bulk Edit Details helpers (`horilla/contrib/generics/views/helpers/edit_field.py`)

## Purpose

HTMX views behind the **Edit Details** control on the record details tab
(`details_tab.html`). One button switches the whole field grid into edit mode
with a single Save/Cancel pair (replacing the former per-field pencil cycle).

Routes: `generics:edit_all_fields` (GET) and `generics:update_all_fields` (POST).

All composable classes inherit [`horilla.views.generic.View`](../../../../views/generic.md),
so [`_inherit_view`](../../../../extension/view/inherit.md) extensions apply via
`as_view()` / `resolve_view_class()`.

---

## Classes overview

| Class / helper | Role |
|----------------|------|
| `FieldInfoResolver` | Per-field widget metadata (`get_field_info`) and value apply/parse (`apply_field_value`, date hooks). Never dispatched via `as_view()` — instantiated through `get_field_info_resolver()`. |
| `ExtraFieldsProvider` | Seam for non-model fields (e.g. `cf_*`) via `get_extra_fields` / `apply_extra_field`. Use `get_extra_fields_provider()`. |
| `EditAllFieldsView` | GET: render `partials/edit_all_fields.html` for every editable field in the detail `body`. |
| `UpdateAllFieldsView` | POST: apply all submitted fields, run `check_before_save`, then save (or skip when nothing changed). |
| `build_edit_all_fields_context(...)` | Shared context builder for render and re-render after blocked/failed save. |
| `can_edit_all_fields(request, obj)` | Who may use Edit Details on `obj`: the record page's rule, `HorillaDetailView.check_update_permission`. |
| `save_all_fields(request, obj, section_view, hooks)` | The save of `UpdateAllFieldsView.post`, shared with other pages that edit a record's fields (the phone app). Returns a `SaveAllFieldsResult`. |

---

## `FieldInfoResolver`

```python
from horilla.contrib.generics.views.helpers.edit_field import get_field_info_resolver

resolver = get_field_info_resolver()  # resolve_view_class(FieldInfoResolver)()
```

Common `get_field_info` keys: `name`, `verbose_name`, `field_type`, `value`,
`display_value`, `choices`, `use_select2`, `input_attrs`.

### Field-type mapping (highlights)

- M2M / FK / choices / boolean / phone / email / url / number as before.
- `DateTimeField` → `datetime-local`; display via `format_datetime_value(..., convert_timezone=False)`.
- `DateField` → `date`; same formatter for display.
- State/country CharFields use model `STATE_FIELD_NAME` / `COUNTRY_FIELD_NAME` when set.
- Extensions may set `input_attrs` (e.g. Jalali `data-jdp`) and change `field_type` to `text`.

### Parse hooks (calendar extensions)

```python
def parse_datetime_field_value(self, value, user=None): ...
def parse_date_field_value(self, value, user=None): ...
```

Gregorian defaults use `datetime.fromisoformat`. Override via `_inherit_view` on
`FieldInfoResolver` (Jalali: `JalaliFieldInfoResolverExtension`).

---

## `ExtraFieldsProvider`

Defaults return no extras / ignore unknown POST keys. Extensions (Custom Fields)
override:

- `get_extra_fields(obj, request, can_update)` → list of `{"info": ..., "editable": bool}`
- `apply_extra_field(obj, name, request)` → `True` if handled (saves immediately)

---

## `EditAllFieldsView`

- HTMX-only (`@htmx_required`)
- Template: `partials/edit_all_fields.html`
- Allowed by `can_edit_all_fields(request, obj)` (see [Who may edit](#who-may-edit))
- Builds field list from the detail section `body`, field permissions, and
  `ExtraFieldsProvider`
- Optional query: `pipeline_field`, `return_url` (validated with
  `url_has_allowed_host_and_scheme`)

```python
from horilla.contrib.generics.views.helpers.edit_field import get_edit_all_fields_view

view = get_edit_all_fields_view()
```

---

## `UpdateAllFieldsView`

- HTMX-only; success re-renders `details_tab.html`
- Allowed by `can_edit_all_fields(request, obj)`, like `EditAllFieldsView`
- The save is [`save_all_fields`](#save_all_fields), called with the view
  itself as `hooks`
- Two-phase save: apply values in-memory (`save=False` except M2M, which commit
  immediately), then `check_before_save(request, obj, changed_fields)`, then
  `obj.save(force=m2m_changed)` when there is something to persist
- **A value that can't be applied:** nothing is saved (M2M aside), and the
  bulk-edit form comes back open with what was typed (`keep_posted_value`),
  each error under its field and a message per field by its label, shown at
  once (the form includes `messages.html`)
- **No-op skip:** if `changed_fields` is empty (and no field errors), skips
  `check_before_save` and `obj.save()` and just re-renders the details tab
- M2M-only changes still bump audit via `force=True` when needed

### Extension seams

| Method | Role |
|--------|------|
| `check_before_save(request, obj, changed_fields)` | Return an `HttpResponse` to block commit (e.g. Duplicates warning); `None` to proceed. |
| `get_allowed_fields(request, obj)` | Narrow which fields may be saved, for the desktop and every `save_all_fields` caller (Approvals: the pending-edit policy). `None` = no limit; defaults to `request.bulk_edit_allowed_fields`. |
| `handle_save_error(request, obj, error, app_label, model_name)` | Customize `ValidationError` from `obj.save()` (e.g. Approvals pending-edit guard). |

---

## `save_all_fields`

```python
from horilla.contrib.generics.views.helpers.edit_field import (
    get_update_all_fields_view,
    save_all_fields,
)

result = save_all_fields(request, obj, section_view, get_update_all_fields_view())
```

The body of `UpdateAllFieldsView.post`, for any page that edits a record's
fields; the phone app (`horilla.contrib.mobile`) calls it too. The caller
checks `can_edit_all_fields` first and passes the Details tab view of `obj`
(`section_view`) and the `UpdateAllFieldsView` whose hooks run: the view
itself, or `get_update_all_fields_view()` (with its `_inherit_view`
extensions) elsewhere.

1. Every field of `section_view.get_effective_body()` that was posted, that
   the user may `readwrite` and that isn't in `non_editable_fields` is
   applied with `apply_field_value(..., save=False)`; many-to-many values are
   written at once.
2. Any other posted name goes to `ExtraFieldsProvider.apply_extra_field`
   (custom fields, saved at once).
3. When every value applied and something changed: `hooks.check_before_save`,
   then `obj.save()`, and a `ValidationError` goes to
   `hooks.handle_save_error`.

`SaveAllFieldsResult`:

| Attribute | Meaning |
|-----------|---------|
| `errors` | field name → message for values that couldn't be applied; the record isn't saved then |
| `changed_fields` | the fields whose value changed |
| `response` | the answer of a hook that stopped the save (`check_before_save`) or took over a failed one (`handle_save_error`) |
| `save_error` | a `ValidationError` from `obj.save()` that no hook handled |
| `ok` | no errors, no hook response, no save error (also when nothing changed) |

`UpdateAllFieldsView` returns `response` as is, re-renders the bulk-edit form
with `save_error`, and adds `errors` as messages. Another page shows its own
answer: the hooks' responses are desktop markup.

---

## Who may edit

`can_edit_all_fields(request, obj)` applies the record page's own rule,
`HorillaDetailView.check_update_permission`, which also decides whether the
Edit Details button and the stage bar are offered:

- an owner of the record (an `OWNER_FIELDS` entry names the user or someone
  in a role below theirs, or access was granted) with `change_own_<model>`;
- anyone with `change_<model>`;
- never a locked record (`is_record_locked`): the form and the save answer
  "This record is read-only." first.

Other users get "You do not have permission to edit this." (`403` on save).

---

## Date/time update rules

- `DateTimeField`: `parse_datetime_field_value`, then user-TZ → default TZ for storage.
- `DateField`: `parse_date_field_value`.

---

## Related

- Details tab UI: [`details.md`](../details.md) · template `details_tab.html`
- [`_inherit_view`](../../../../extension/view/inherit.md)
- [`DateTimeFormatter`](../../formatting/datetime.md) / [`_inherit_formatter`](../../../../extension/formatting/inherit.md)
- Consumers: Custom Fields (`ExtraFieldsProvider`), Duplicates / Approvals
  (`UpdateAllFieldsView` hooks), Jalali (`FieldInfoResolver`)

---

## Summary

Bulk Edit Details backend for detail tabs: one form for all editable fields,
extension-aware parse/display/extra fields, pre-save and save-error seams, and
skipped no-op saves when nothing actually changed.
