# Horilla Shortcuts

## 🎯 Purpose

`horilla.shortcuts` provides small helper shortcuts that wrap or re-export common Django shortcuts.

In this repo, it mainly includes:
- a convenience object fetcher with proper 404 handling: `get_object_or_404`
- re-exported `redirect` and `render` from `django.shortcuts`

This keeps your imports consistent (and lets Horilla control the error message/exception type for `get_object_or_404`).

---

## 📦 Module location

```text
horilla/shortcuts/
├── __init__.py          # re-exports: redirect, render, get_object_or_404
└── query_helpers.py    # get_object_or_404 implementation
```

---

## 🔁 What it provides

### 📍 Re-exported Django shortcuts (`horilla.shortcuts.__init__`)

These names are imported from Django shortcuts and exported:

- `redirect`
- `render`

So you can do:

```python
from horilla.shortcuts import redirect, render
```

Use these re-exports in views and HTMX partial handlers (for example `ForgotPasswordView` in core) instead of importing `django.shortcuts` directly.

### ➕ Custom helper: `get_object_or_404`

Defined in `horilla/shortcuts/query_helpers.py`:

```python
from horilla.shortcuts import get_object_or_404
```

---

## 🚫 `get_object_or_404`

### 📍 Function

```python
def get_object_or_404(klass, *args, **kwargs):
    ...
```

### 🎯 Purpose

Use `get()` to fetch an object and:
- return the object if found
- raise `Http404` if no object matches

It’s similar to Django’s common helper pattern, but implemented here with Horilla’s exact behavior:
- uses `django.shortcuts._get_queryset(klass)` to support Model/Manager/QuerySet
- raises `django.http.Http404` with a message based on the model’s `verbose_name`

### ✅ Accepted `klass` types

`klass` can be:
- a Model class
- a Manager
- a QuerySet

If `klass` is not one of these (i.e. the derived queryset doesn’t have `.get`), it raises `ValueError`.

### 🔄 Behavior details

- Calls `queryset.get(*args, **kwargs)`
- If nothing exists, catches `queryset.model.DoesNotExist` and raises:

```text
Http404("No <model verbose_name> matches the given query.")
```

### 🧪 Example: Model class

```python
from horilla.shortcuts import get_object_or_404
from horilla_crm.contacts.models import Contact

contact = get_object_or_404(Contact, pk=contact_id)
```

### 🧪 Example: Manager

```python
contact = get_object_or_404(
    Contact.objects,
    pk=contact_id,
)
```

### 🧪 Example: QuerySet

```python
qs = Contact.objects.filter(is_active=True)
contact = get_object_or_404(qs, pk=contact_id)
```

---

## 📌 Import patterns

### Typical view usage

```python
from horilla.shortcuts import get_object_or_404, render, redirect


def my_view(request, contact_id):
    contact = get_object_or_404(Contact, pk=contact_id)
    return render(request, "contact.html", {"contact": contact})
```
