# Horilla utilities (`horilla.utils`)

## Purpose

Top-level **`horilla.utils`** holds small, cross-cutting helpers: branding defaults, form/field choice tuples, upload path generation, version aggregation for installed apps, plus subpackages/modules for **decorators**, **translation**, **HTML**, **text**, and **functional** re-exports.

This is **not** the Django app `horilla.contrib.utils` (that package lives under `horilla/contrib/utils/`). Import paths here are `horilla.utils.*`.

---

## Module layout (on disk)

Layout under `horilla/utils/` matches the repository (after the package is used locally, Python may also create `__pycache__/` directories; those are generated and are not source).

```text
horilla/utils/
├── decorators/       # View decorators (permissions, HTMX, DB init). See docs below.
├── translation/      # Re-exports Django translation API under one import path.
├── html.py           # Re-exports django.utils.html (format_html, escape, …)
├── text.py           # Re-exports django.utils.text (slugify, Truncator, …)
├── functional.py     # Re-exports django.utils.functional (cached_property, lazy, …)
├── timezone.py       # Re-exports django.utils.timezone (now, localtime, make_aware, …)
├── branding.py       # DEFAULTS + load_branding() from optional settings.BRANDING_MODULE
├── choices.py        # TIMEZONE_CHOICES, LANGUAGE_CHOICES, format/operator tuples, FIELD_TYPE_MAP, …
├── upload.py         # upload_path(instance, filename) for namespaced FileField paths
├── version.py        # get_module_version_info, collect_all_versions (reads `__version__` modules)
└── __init__.py       # Empty placeholder (no re-exports at package root)
```

| Path | Role |
|------|------|
| `decorators/` | `permission_required`, `htmx_required`, `db_initialization`, etc. Documented in [decorators.md](./decorators.md). |
| `translation/` | `gettext_lazy`, `gettext`, `activate`, … from Django. Documented in [translation.md](./translation.md). |
| `html.py` | `format_html`, `format_html_join`, `escape`, `strip_tags`, … from Django. Documented in [html.md](./html.md). |
| `text.py` | `slugify`, `Truncator`, `capfirst`, … from Django. Documented in [text.md](./text.md). |
| `functional.py` | `cached_property`, `lazy`, `Promise`, … from Django. Documented in [functional.md](./functional.md). |
| `timezone.py` | `now`, `localtime`, `make_aware`, `UTC`, … from Django. Use `from horilla.utils import timezone`. |
| `branding.py` | `DEFAULTS` (title, login copy, logo paths) and `load_branding()` merging overrides from `BRANDING_MODULE`. Also used as the fallback **company name** in activity meeting and booking transactional emails when no company is set. |
| `choices.py` | Shared `(value, label)` tuples and maps (languages, date/time formats, operators, field types, `BLOCKED_EXTENSIONS`). |
| `upload.py` | Builds `app_label/model_name/[field_name/]slug-uuid.ext` paths to avoid collisions. |
| `version.py` | Discovers `module.__version__` metadata and changelog attributes like `__1_2_0__` for about/settings UIs. |
| `__init__.py` | Intentionally empty; import from submodules or specific modules (e.g. `from horilla.utils.choices import LANGUAGE_CHOICES`). |

---

## Deeper docs

- [Decorators](./decorators.md) — `horilla.utils.decorators`
- [Translation](./translation.md) — `horilla.utils.translation`
- [HTML](./html.md) — `horilla.utils.html`
- [Text](./text.md) — `horilla.utils.text`
- [Functional](./functional.md) — `horilla.utils.functional`

### Timezone (`horilla.utils.timezone`)

Prefer Horilla imports over `django.utils.timezone`:

```python
from horilla.utils import timezone

now = timezone.now()
aware = timezone.make_aware(naive_dt)
```

Also available as named imports: `from horilla.utils.timezone import now, localtime, UTC`.

---

## Quick import examples

```python
from horilla.utils.branding import load_branding, DEFAULTS
from horilla.utils.choices import LANGUAGE_CHOICES, OPERATOR_CHOICES
from horilla.utils.upload import upload_path
from horilla.utils.version import collect_all_versions, get_module_version_info
from horilla.utils.decorators import permission_required, htmx_required
from horilla.utils.translation import gettext_lazy as _
from horilla.utils.html import format_html, escape, strip_tags
from horilla.utils.text import slugify
from horilla.utils.functional import cached_property
from horilla.utils import timezone
```
