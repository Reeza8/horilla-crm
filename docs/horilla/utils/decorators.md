# Horilla Decorators (`horilla.utils.decorators`)

## 🎯 Purpose

`horilla.utils.decorators` contains reusable decorators for:

- **Permission checks** (with either silent denial or rendering a 403 template)
- **HTMX-only endpoints**
- **Database initialization gating** (only allow a view when DB is not initialized and a session password matches)

The public exports are defined in `horilla/utils/decorators/__init__.py`.

---

## 📦 Module location

```text
horilla/utils/decorators/
├── __init__.py   # re-exports: method_decorator + decorators below
├── wrapper.py    # implementations

```

---

## 🔁 What `horilla.utils.decorators` exports

From `horilla/utils/decorators/__init__.py`:

- `method_decorator` (re-export from `django.utils.decorators`)
- `permission_required_or_denied`
- `permission_required`
- `htmx_required`
- `db_initialization`

Import pattern:

```python
from horilla.utils.decorators import (
    method_decorator,
    permission_required_or_denied,
    permission_required,
    htmx_required,
    db_initialization,
)
```

---

## 🔐 `permission_required_or_denied`

### 📍 Function

```python
permission_required_or_denied(
    perms,
    template_name="403.html",
    require_all=False,
    modal=False,
    embed=None,
)
```

### 🎯 Purpose

Guard a view (FBV or CBV) by permissions and:

- if unauthenticated: **redirect** to login (`horilla_core:login`) with `?next=<request.path>`
- if authenticated and allowed: run the view
- if authenticated but denied: **render** a template (default `403.html`)

### ✅ Behavior details

- `perms` can be a string or list/tuple; it is normalized to a list.
- Permission logic:
  - `require_all=True` → `user.has_perms(perms)`
  - `require_all=False` → `user.has_any_perms(perms)`
- Context passed to the template:
  - `{"permissions": perms, "modal": modal}`
  - `embed` may be set to `True` automatically when:
    - `modal` is `False`, and
    - request is HTMX (`request.META["HTTP_HX_REQUEST"]`), and
    - `embed` is not explicitly `False`

### 🧪 Usage example (FBV, explicit args)

```python
from horilla.utils.decorators import permission_required_or_denied


@permission_required_or_denied(
    perms=["contacts.view_contact"],
    template_name="403.html",
    require_all=False,
    modal=False,
    embed=None,
)
def contact_list(request):
    ...
```

### 🧪 Usage example (CBV, explicit args)

```python
from horilla.utils.decorators import method_decorator, permission_required_or_denied


@method_decorator(
    permission_required_or_denied(
        perms=["contacts.add_contact"],
        template_name="403.html",
        require_all=False,
        modal=True,
        embed=None,
    ),
    name="dispatch",
)
class ContactCreateView(View):
    ...
```

---

## 🔐 `permission_required`

### 📍 Function

```python
permission_required(
    perms,
    require_all=False,
)
```

### 🎯 Purpose

Guard a view by permissions, but **do not render an error template**:

- unauthenticated → redirect to login
- denied → return `HttpResponse("")` (empty response)
- allowed → run the view

This is used when the UI expects “no content” instead of a full 403 page/fragment.

### 🧪 Usage example (explicit args)

```python
from horilla.utils.decorators import permission_required


@permission_required(
    perms=["reports.view_report"],
    require_all=False,
)
def report_partial(request):
    ...
```

---

## ⚡ `htmx_required`

### 📍 Function

```python
htmx_required(
    view_func=None,
    login=True,
)
```

### 🎯 Purpose

Ensure a view is accessed via **HTMX**.

Behavior:
- if `login=True` and user is not authenticated → redirect to login with `?next=<request.path>`
- if request is not HTMX (`request.headers["HX-Request"] != "true"`) → render `405.html`
- else → run the view

### 🧪 Usage example (no-args form)

```python
from horilla.utils.decorators import htmx_required


@htmx_required
def modal_form(request):
    ...
```

### 🧪 Usage example (with args, explicit)

```python
from horilla.utils.decorators import htmx_required


@htmx_required(
    view_func=None,
    login=False,
)
def public_htmx_fragment(request):
    ...
```

---

## 🔒 `db_initialization`

### 📍 Function (decorator factory)

```python
db_initialization(model=None)
```

### 🎯 Purpose

Allow a view to run **only** when:
- the database still needs initialization (`not model.objects.exists()`), and
- the session password matches `settings.DB_INIT_PASSWORD`

Otherwise it redirects to a safe `next` URL using **`safe_url`** from **`horilla.web`**:

```python
from horilla.web import safe_url

safe_url(request, request.GET.get("next", "/"))
```

### ✅ Behavior details

- Reads expected password from: `settings.DB_INIT_PASSWORD`
- Reads provided password from session key: `request.session["db_password"]`
- If DB is already initialized OR password invalid → redirects away

**Related:** Full init wizard, **Go To Home**, and `initialize_database_go_home` are documented in [Initialize Database](../contrib/core/initialize_database.md).

### 🧪 Usage example (CBV, explicit)

```python
from django.contrib.auth import get_user_model
from horilla.utils.decorators import method_decorator, db_initialization

User = get_user_model()


@method_decorator(
    db_initialization(
        model=User,
    ),
    name="dispatch",
)
class InitSetupView(View):
    ...
```
