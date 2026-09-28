# Horilla Attachments Views (`horilla_generics/views/attachments.py`)

## 🎯 Purpose

`attachments.py` provides HTMX-friendly views for the **Notes & Attachments** feature:

- list attachments linked to any model object
- open attachment details in modal
- create/edit attachment records with file upload
- delete attachment records

It integrates with:
- `HorillaAttachment` and `HorillaContentType` (from `horilla_core.models`)
- generic list/detail/delete view infrastructure in `horilla_generics`
- template set:
  - `notes_attachments.html`
  - `notes_attachments_detail.html`
  - `forms/notes_attachment_form.html`

### XSS sanitization on save

`HorillaAttachment.save()` sanitizes user-controlled text before persist:

- **`title`** → `sanitize_plain_text()` (no HTML)
- **`description`** → `sanitize_html()` (bleach allowlist)

Helpers live in `horilla.contrib.utils.methods` — see [../../utils/utils.md](../../utils/utils.md). The form may also escape for the editor; model `save()` is the durable XSS control for stored attachments.

---

## 📦 Module components

Classes in this file:

1. `AttachmentListView(HorillaListView)`
2. `HorillaNotesAttachementSectionView(DetailView)`
3. `HorillaNotesAttachementDetailView(HorillaModalDetailView)`
4. `HorillaNotesAttachmentCreateView(FormView)`
5. `HorillaNotesAttachmentDeleteView(HorillaSingleDeleteView)`

> Note: class names contain `Attachement` spelling (as in the source code).

---

## 🔁 `AttachmentListView`

### Purpose

Reusable list configuration for displaying `HorillaAttachment` rows.

### Key settings

```python
model = HorillaAttachment
columns = ["title", "created_by", "created_at"]
bulk_select_option = False
list_column_visibility = False
table_height_as_class = "h-[calc(_100vh_-_520px_)]"
table_width = False
```

This class is not directly exposed as URL endpoint; it is instantiated by `HorillaNotesAttachementSectionView.get(...)` to render attachments inside the tab section.

---

## 🔍 `HorillaNotesAttachementSectionView`

### Decorators / access

- `@htmx_required`
- `@permission_required_or_denied(["horilla_core.view_horillaattachment", "horilla_core.view_own_horillaattachment"])`

### Purpose

Renders the notes/attachments section for a specific object (`pk`) in detail tabs.

### Template

- `template_name = "notes_attachments.html"`
- `context_object_name = "obj"`

### Important methods

#### `get_actions()`

Returns row actions for attachment list:
- View
- Edit
- Delete

These include HTMX attrs such as `hx-get`, `hx-post`, modal targets, and permission metadata consumed by generic list templates.

#### `check_attachment_add_permission()`

Evaluates whether current user may add attachments for the related object:

- requires `horilla_core.add_horillaattachment`
- and either:
  - owner-style permission `change_own_<model>` when user is in one of `OWNER_FIELDS`
  - or standard `change_<model>`

Handles owner checks for:
- FK owner fields
- ManyToMany owner fields

#### `get(...)`

Flow:
1. resolve object (`self.get_object()`)
2. resolve content type via `HorillaContentType.objects.get_for_model(self.model)`
3. query attachments by `(content_type, object_id)`
4. store attachment ids in session: `ordered_ids_horillaattachment`
5. instantiate `AttachmentListView`, inject request/queryset/actions/view_id
6. merge list context + detail context
7. set `can_add_attachment`
8. render `notes_attachments.html`

### Key context variables for `notes_attachments.html`

| Variable | Example |
|---|---|
| `obj` | related object instance (ex: Lead object) |
| `can_add_attachment` | `True` |
| `view_id` | `"attachments_lead_42"` |
| list-view context (`queryset`, `actions`, etc.) | provided by `AttachmentListView.get_context_data()` |

---

## 🧾 `HorillaNotesAttachementDetailView`

### Decorators / access

- `@htmx_required`
- `@permission_required_or_denied(["horilla_core.view_horillaattachment", "horilla_core.view_own_horillaattachment"])`

### Base / template

- inherits `HorillaModalDetailView`
- `model = HorillaAttachment`
- `template_name = "notes_attachments_detail.html"`
- `title = "Notes and Attachment"`

### `get(...)` behavior

- tries `self.get_object()`
- if missing:
  - pushes error message
  - returns script response to reload and close content modal
- else renders normal modal detail context

### Important template variables (`notes_attachments_detail.html`)

| Variable | Example |
|---|---|
| `object` | `HorillaAttachment` instance |
| `instance_ids` | list for prev/next navigation |
| `previous_url` / `next_url` / `ids_key` | used for modal navigation buttons |
| `request.GET.urlencode` | preserved params for navigation |- unsupported dimension -> returns error


---

## 📝 `HorillaNotesAttachmentCreateView`

### Decorator / access

- `@htmx_required`
- inherits `LoginRequiredMixin`, `FormView`

### Base settings

- `template_name = "forms/notes_attachment_form.html"`
- `form_class = HorillaAttachmentForm`
- `model = HorillaAttachment`

### Create vs edit mode

- create: no `pk` in URL kwargs
- edit: `pk` exists

#### `get_context_data(...)`

Sets `form_url`:
- create: `reverse_lazy("horilla_generics:notes_attachment_create")`
- edit: `reverse_lazy("horilla_generics:notes_attachment_edit", kwargs={"pk": pk})`

#### `get_object()`

Returns attachment object for edit mode, otherwise `None`.

#### `get_form(...)`

Binds `instance=obj` for edit mode.

### Permission logic (`dispatch`)

#### Edit mode (`pk` given)

- load attachment + related object
- call `check_related_object_permission(related_object, "change")`
- deny => error message + JS response to close modal/reload UI

#### Create mode

Reads from query params:
- `model_name`
- `object_id`

Then:
- resolves `HorillaContentType` by model name
- loads related object
- checks `check_related_object_permission(..., "add")`
- deny/invalid => error message + JS response

### `form_valid(...)`

On create:
- resolves content type from `model_name` GET param
- sets:
  - `created_by = request.user`
  - `object_id = request.GET["object_id"]`
  - `content_type`
  - `company = request.active_company`
- success message: `"<title> created successfully"`

On edit:
- updates existing object
- success message: `"<title> updated successfully"`

Returns JS response:
- triggers notes tab reload and closes modal

### Required create query params (example)

When opening create modal, frontend should include:

```text
?model_name=lead&object_id=42
```

Template (`notes_attachments.html`) does:

```html
hx-get="{% url 'horilla_generics:notes_attachment_create' %}?{{ request.GET.urlencode }}&model_name={{obj|model_name}}"
```

---

## 🗑️ `HorillaNotesAttachmentDeleteView`

### Decorators / access

- `@htmx_required`
- `@permission_required_or_denied("horilla_core.delete_horillaattachment", modal=True)`

### Base / model

- inherits `HorillaSingleDeleteView`
- `model = HorillaAttachment`

### Post-delete response

`get_post_delete_response()` returns script that:
- triggers `#reloadButton`
- closes content modal

---

## 🧪 End-to-end usage example

### 1) Add URLs (example pattern)

```python
path(
    "leads-notes-attachments/<int:pk>/",
    LeadsNotesAndAttachments.as_view(model=Lead),
    name="leads_notes_attachments",
)
```

### 2) Tab opens section view

Section view renders:
- header + add button (`can_add_attachment`)
- embedded list (`list_view.html`) with attachment rows and actions

### 3) User clicks Add

Modal GET:

```text
/generics/notes-attachment-create/?model_name=lead&object_id=42
```

Form posts to `form_url` with multipart upload.

### 4) Save response

View returns JS snippet to:
- click notes tab reload button
- close modal
- refresh detail container

---

## 📌 Practical notes

- Ownership checks rely on related model’s `OWNER_FIELDS`. If your model needs owner-aware attachment permissions, define `OWNER_FIELDS` properly.
- `model_name` for create path is looked up via `HorillaContentType.objects.get(model=model_name.lower())`; pass canonical model name.
- All flows are HTMX-oriented; non-HTMX access is rejected by `htmx_required`.
