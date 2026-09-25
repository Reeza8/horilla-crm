# Multi-step form view (`horilla_generics/views/multi_form.py`)

## Purpose

`HorillaMultiStepFormView` is the generic **wizard-like create/update form** for Horilla.

It supports:

- multi-step field grouping (`step_fields` from form class),
- create and edit in the same view,
- step-wise session persistence,
- file/image persistence across steps (base64 in session),
- many-to-many presewrvation between steps,
- field-level permission wiring,
- dynamic-create related-field controls,
- create/update permission + own-object checks (via shared mixin),
- HTMX-first responses (`form_view.html`, modal close/reload scripts, optional HX redirect).

---

## Class and defaults

```python
class HorillaMultiStepFormView(FormViewCommonMixin, FormView):
```

Key defaults:

| Attribute | Default | Role |
|-----------|---------|------|
| `template_name` | `form_view.html` | Main multi-step template. |
| `form_class` | `None` | If absent and `model` exists, dynamic `HorillaMultiStepForm` subclass is built. |
| `model` | `None` | Required for dynamic form generation and save logic. |
| `total_steps` | `4` | Maximum wizard steps. |
| `step_titles` | `{}` | Labels shown per step. |
| `fullwidth_fields` | `[]` | Field names rendered full-width. |
| `dynamic_create_fields` | `[]` | FK/M2M fields eligible for inline dynamic creation. |
| `dynamic_create_field_mapping` | `{}` | Per-field config for dynamic create behavior/permissions/initials. |
| `pk_url_kwarg` | `"pk"` | URL kwarg for edit mode object lookup. |
| `permission_required` | `None` | Optional explicit permission(s); otherwise auto add/change permissions. |
| `check_object_permission` | `True` | Object-level own-permission checks via mixin helpers. |
| `skip_permission_check` | `False` | Bypass all permission checks when needed. |
| `single_step_url_name` | `None` | URL config for alternate single-form mode. |
| `detail_url_name` | `None` | On create success, optional HX redirect target to detail page. |
| `save_and_new` | `True` | Show/create "save and new" workflow on final step. |

---

## Shared mixin behavior used here

`FormViewCommonMixin` provides reusable pieces used heavily by this class:

- `has_permission()` and auto permission generation (`add/change`, `*_own_*`),
- object resolution with safe HTMX reload response,
- `get_filtered_dynamic_create_fields()` (permission-aware FK/M2M dynamic create),
- `get_field_permissions()` (field-level visibility/editability map),
- alternate form URL helper (`get_alternate_form_url`) for single <-> multi switching.

So `HorillaMultiStepFormView` focuses on **wizard state and save flow**, while common auth/object logic stays centralized.

---

## Lifecycle overview

### 1) `dispatch`

1. Runs permission check unless `skip_permission_check`.
2. Resolves object from URL `pk` (edit mode) using mixin helper.
3. If editing, sets:
   - `self.object`
   - object-scoped storage key: `ClassName_form_data_<pk>`
4. Calls parent dispatch.

### 2) `get`

- Resets session data when:
  - `?reset=...`, or
  - `?new=...` in create mode.
- In edit mode, opening step 1 without "previous" also clears stale wizard session.
- Initializes `current_step = 1`, builds form, renders context.

### 3) `post`

- If `"previous"` button clicked: decrements step and re-renders prior step from session data/files.
- Otherwise follows normal FormView POST (`form_valid` / `form_invalid`).

---

## Session storage model

Per-view key:

- `self.storage_key = "<ClassName>_form_data"` (or `<ClassName>_form_data_<pk>` in edit)

Files key:

- `f"{self.storage_key}_files"`

Cleanup:

- `cleanup_session_data()` removes both keys and marks session modified.

This separation allows step state to survive page transitions while keeping binary file data compactly encoded.

---

## File handling across steps

### Why custom file handling exists

HTTP uploads are request-scoped. In step wizards, previously uploaded files disappear unless persisted server-side.

### How it works

- `encode_file_for_session(uploaded_file)`:
  - reads bytes,
  - stores base64 content + metadata (`name`, `content_type`, `size`).
- `decode_file_from_session(file_data)`:
  - decodes base64,
  - recreates `SimpleUploadedFile`.

`get_form_kwargs()` merges:

1. current request files (`request.FILES`)
2. decoded session files (for earlier steps)

Final save explicitly handles file fields:

- clear flag (`<field>_cleared`) -> set `None`
- new/uploaded file -> assign
- previous-step file -> assign from decoded files

---

## Step management and form kwargs

### Step detection

`get_initial_step()` reads `POST["step"]` with validation and bounds `[1, total_steps]`.

### Concrete form + extensions

When `form_class` is set (e.g. `UserFormClass`), `get_form_class()` calls `resolve_form_class()` so `_inherit_form` extensions compose before the wizard runs (e.g. `UserFormClassExtended`).

### Dynamic form fallback

If `form_class` is not set and `model` exists, `get_form_class()` creates a local `DynamicMultiStepForm`:

- `model = self.model`
- `fields = "__all__"`
- excludes audit/meta fields (`created_at`, `updated_at`, etc.)
- auto date widgets for `DateField`.

### `get_form_kwargs()` responsibilities

This is the densest method in the class. It:

1. injects:
   - `request`
   - `step`
   - `full_width_fields`
   - filtered dynamic-create fields
   - field permissions
   - `instance` in edit mode
2. loads session `form_data` and `files_data`
3. builds maps of all step fields from `form_class.step_fields`
4. repairs certain malformed M2M session values (stringified list edge case)
5. ingests current POST values into session, with type-aware handling:
   - booleans,
   - M2M lists (preserve previous-step values when not present in current post),
   - date/datetime parsing,
   - decimal normalization.
6. persists file clear/upload state flags.
7. writes updated form/files back into session.
8. attaches `data`/`form_data`/`files` kwargs for form reconstruction.
9. prevents binding in navigation scenarios (`previous` or intermediate step transitions) by clearing `data` when appropriate.

---

## Context model (`get_context_data`)

Adds wizard + UI metadata:

- `step_titles`, `total_steps`, `current_step`
- `form_title` (`Create <verbose>` / `Update <verbose>`)
- `object`, `is_edit`
- `full_width_fields`
- dynamic create config:
  - `dynamic_create_fields`
  - `dynamic_create_field_mapping`
  - `related_models_info`
- current and stored session snapshots:
  - `stored_form_data`
  - `stored_files_data`
  - `file_field_states` (existing/new/cleared flags + filename)
- `single_step_url`
- `view_id`
- `field_permissions`
- resolved `form_url` (create or edit endpoint)

It also annotates form widgets with `fullwidth` attr for configured fields.

---

## Validation and save flow (`form_valid`)

Two branches:

### A) Intermediate step (`step < total_steps`)

1. Increments `current_step`.
2. Rebuilds next-step form from session data/files.
3. Clears bound errors for navigation UX.
4. Re-renders next step without saving model.

### B) Final step

1. Merges session + POST + file data.
2. Creates `final_form` with all accumulated data.
3. If valid:
   - `instance = final_form.save(commit=False)`
   - ensures company assignment from form / active company / user company fallback
   - explicitly applies file-field decisions
   - `instance.save()`
   - `final_form.save_m2m()`
   - applies explicit M2M set/clear from accumulated `form_data`
   - clears wizard session
   - shows success message (`created` or `updated`)
4. Returns one of:
   - save-and-new HTMX payload (create mode + `save_and_new` button),
   - `HX-Redirect` to `detail_url_name` (create mode),
   - reload+close script.

If final validation or save fails:

- rebuilds error form,
- keeps step at final step,
- re-renders with errors while preserving accumulated data.

---

## Permission model

By default (unless overridden):

- create mode -> requires `add_<model>` or `add_own_<model>`
- edit mode -> requires `change_<model>` or `change_own_<model>` + object ownership check
- superuser bypass allowed

You can override with:

- `permission_required` (string or list),
- `skip_permission_check = True` (not recommended unless wrapped externally).

Denied access returns `permission_denied_template` (default `403.html`, modal context).

---

## URLs and alternate form modes

### `get_create_url()`

Resolves create URL from `form_url_name` (string or dict `{create, edit}`), else request path.

### `get_single_step_url()`

Uses `single_step_url_name` through mixin helper to generate alternate single-form endpoint.

This allows a UI toggle between:

- multi-step wizard (`HorillaMultiStepFormView`)
- single-step form (`HorillaSingleFormView`)

---

## Real examples from codebase

### 1) Leads multi-step form

`LeadFormView` (`horilla_crm/leads/views/lead_actions.py`) sets:

- `form_class = LeadFormClass`
- `model = Lead`
- `fullwidth_fields = ["requirements"]`
- `dynamic_create_fields = ["lead_status"]`
- custom `dynamic_create_field_mapping` for lead status defaults
- `single_step_url_name` mapping
- `detail_url_name = "leads:leads_detail"`
- step titles for all 4 steps
- `@method_decorator(transaction.atomic, name="form_valid")` so assignment-rule
  `on_commit` callbacks run after `save_m2m()` (custom fields readable on create);
  `LeadsSingleFormView` uses the same decorator — see
  [assignment_rule.md](../../../../horilla_crm/leads/assignment_rule.md#create-vs-edit-custom-fields-and-post_save-timing)

### 2) Other apps reusing the same base

Also used by:

- accounts (`AccountFormView`)
- contacts (`ContactFormView`, `RelatedContactFormView`)
- campaigns (`CampaignFormView`)
- opportunities (`OpportunityMultiStepFormView`, `RelatedOpportunityFormView`)
- core branch/company multi forms (`CompanyMultiFormView`)
- users (`UserFormView`)

This confirms the class is the shared wizard foundation across CRM/core domains.

---

## Practical examples

### Example 1: Basic multi-step create/update view

```python
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils.decorators import method_decorator
from horilla.utils.decorators import htmx_required, permission_required_or_denied
from horilla.urls import reverse_lazy
from horilla_generics.views.multi_form import HorillaMultiStepFormView
from myapp.forms import TicketMultiStepForm
from myapp.models import Ticket, TicketStage


@method_decorator(htmx_required, name="dispatch")
@method_decorator(
    permission_required_or_denied(["myapp.view_ticket", "myapp.view_own_ticket"]),
    name="dispatch",
)
class TicketFormView(LoginRequiredMixin, HorillaMultiStepFormView):
    model = Ticket
    form_class = TicketMultiStepForm
    total_steps = 3
    step_titles = {
        "1": "Basic Information",
        "2": "Assignment",
        "3": "Confirmation",
    }
    form_url_name = {"create": "myapp:ticket_create", "edit": "myapp:ticket_edit"}
    single_step_url_name = {
        "create": "myapp:ticket_create_single",
        "edit": "myapp:ticket_edit_single",
    }
    detail_url_name = "myapp:ticket_detail"
    fullwidth_fields = ["description"]
    dynamic_create_fields = ["stage"]
    dynamic_create_field_mapping = {
        "stage": {
            "fields": ["name", "order", "color"],
            "initial": {"order": TicketStage.get_next_order_for_company},
        }
    }
    view_id = "ticket-form-view"
```

---

### Example 2: Matching URL patterns

```python
# myapp/urls.py
from horilla.urls import path
from myapp import views

app_name = "myapp"

urlpatterns = [
    path("ticket/create/", views.TicketFormView.as_view(), name="ticket_create"),
    path("ticket/edit/<int:pk>/", views.TicketFormView.as_view(), name="ticket_edit"),
    path(
        "ticket/create-single/",
        views.TicketSingleFormView.as_view(),
        name="ticket_create_single",
    ),
    path(
        "ticket/edit-single/<int:pk>/",
        views.TicketSingleFormView.as_view(),
        name="ticket_edit_single",
    ),
    path("ticket/<int:pk>/", views.TicketDetailView.as_view(), name="ticket_detail"),
]
```

---

### Example 3: Form class with step fields

```python
from horilla_generics.forms import HorillaMultiStepForm
from myapp.models import Ticket


class TicketMultiStepForm(HorillaMultiStepForm):
    class Meta:
        model = Ticket
        fields = [
            "title",
            "description",
            "priority",
            "stage",
            "owner",
            "due_date",
        ]

    # Required for wizard behavior
    step_fields = {
        1: ["title", "description", "priority"],
        2: ["stage", "owner"],
        3: ["due_date"],
    }
```

---

### Example 4: Typical HTMX open + save flow

```html
<!-- Open create form in modal -->
<button
  hx-get="{% url 'myapp:ticket_create' %}"
  hx-target="#modalBox"
  hx-swap="innerHTML"
  onclick="openModal()">
  Create Ticket
</button>
```

Inside the form UI (handled by `form_view.html`), the wizard posts:

- `step=1` + fields -> next step
- `step=2` + fields -> next step
- `step=3` + fields -> final save
- `previous=1` -> previous step render

On final success, this view returns one of:

- `HX-Redirect` to `detail_url_name` (create mode),
- reload + close modal script,
- "save and new" reload/open-create payload.

---

## Extension guidelines

### Minimum subclass setup

- set `model`
- set `form_class` (recommended) or rely on dynamic fallback
- define `step_titles` and `total_steps` to match form `step_fields`
- set `view_id` and URLs (`form_url_name`, `detail_url_name`) for HTMX flows

### If you override `get_form_kwargs`

Always call:

```python
kwargs = super().get_form_kwargs()
```

Then append custom keys; avoid replacing session/file logic.

### If you customize save logic

Prefer extending `form_valid` carefully and keep:

- final form validation,
- file handling,
- `save_m2m`,
- session cleanup.

---

## Related files

| File | Role |
|------|------|
| `horilla_generics/views/toolkit/form_mixin.py` | shared permission/object/dynamic-create helpers |
| `horilla_generics/forms/*` (`HorillaMultiStepForm`) | step field definitions and form behavior |
| `horilla_generics/templates/form_view.html` | multi-step template rendering |

---

## Summary

`HorillaMultiStepFormView` is a robust wizard engine: it preserves partial data across steps, keeps uploads alive across requests, enforces create/update permissions, and provides predictable HTMX responses for modal workflows. Subclasses mostly configure model/form/steps and inherit the rest.
