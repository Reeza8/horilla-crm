# `local_settings.py`

## 🎯 Purpose

`horilla/settings/local_settings.py` is intended for **local overrides**.

In your current repo snapshot, this file may be empty/placeholder, but the expected pattern is:
- developers customize settings per machine/environment here
- base settings remain in `base.py`
- CRM / extra apps are appended in `horilla_apps.py`

## How it is loaded

`horilla/settings/__init__.py` imports in this order:

```python
from horilla.settings.base import *
from horilla.settings import horilla_apps
from horilla.settings.local_settings import *
```

1. **`base.py`** — platform defaults (`INSTALLED_APPS`, middleware, databases, …).
2. **`horilla_apps`** — mutates `INSTALLED_APPS` (and related) for CRM and optional packages; see [horilla_apps.md](horilla_apps.md).
3. **`local_settings.py`** — **last**, so machine/env overrides win over both base and app-extension lists.

Anything you define in `local_settings.py` can override variables imported from `base.py` **and** adjustments made while importing `horilla_apps` (for example reordering or removing apps from `INSTALLED_APPS`, `DEBUG`, `ALLOWED_HOSTS`, database credentials).

> **Why after `horilla_apps`?** App packages may append to `INSTALLED_APPS` at import time. Loading local settings first would let those appends overwrite your local `INSTALLED_APPS` assignment. Importing local settings **last** keeps developer overrides authoritative.

## Example override

```python
# horilla/settings/local_settings.py

DEBUG = False
ALLOWED_HOSTS = ["crm.example.com"]
```

---

If you add variables here, ensure they are compatible with what `base.py` expects.
