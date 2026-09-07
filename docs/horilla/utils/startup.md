# Runserver startup helpers (`horilla.utils.startup`)

## Purpose

`horilla.utils.startup` improves the local `python manage.py runserver` experience:

1. **Progress bar** — shows app load progress (import → models → ready) on one terminal line
2. **Banner** — replaces `Django version …` with `Horilla version …` from `horilla.__version__`

Both are installed from project root `manage.py` before Django starts. No extra `INSTALLED_APPS` entry is required.

---

## Module layout

```text
horilla/utils/startup/
├── __init__.py    # re-exports install_progress, install_banner
├── progress.py    # terminal progress bar during apps.populate()
└── banner.py      # Daphne runserver banner: Horilla version line
```

This page is `docs/horilla/utils/startup.md`.

---

## Wiring (`manage.py`)

```python
from horilla.utils.startup import install_banner, install_progress

install_progress()
install_banner()
```

Failures are swallowed so a broken helper never blocks `runserver`.

---

## Progress bar (`progress.py`)

### When it runs

- Only for `manage.py runserver`
- Autoreloader **parent**: prints a short “starting…” line (no bar)
- Autoreloader **child** (`RUN_MAIN=true`) or `--noreload`: shows the live bar

### How progress is counted

Each installed app contributes **3 steps**:

| Phase | When |
|-------|------|
| `import` | after `AppConfig.__init__` |
| `models` | after `AppConfig.import_models` |
| `ready` | after `AppConfig.ready()` |

So total steps = `len(INSTALLED_APPS) × 3` (for example, 46 apps → 138 steps).

### Example output

```text
Horilla runserver starting (loading Django, progress bar follows)...
Horilla loading [##############----------------]  47% (65/138) models mail
Horilla loading [##############################] 100% (138/138) ready
Horilla apps ready.
```

The bar updates **in place** (one line). At 100%, the app name is omitted (`ready` only), then `Horilla apps ready.` is printed.

### Implementation notes

- Patches `AppConfig.__init__`, `AppConfig.import_models`, and `Apps.populate`
- Ignores later no-op `populate()` calls (system checks / Daphne) once finished
- Writes to `stderr` so it stays visible next to Django logs

---

## Banner (`banner.py`)

### What changes

Only the version line is rewritten. Daphne’s ASGI line is unchanged:

```text
Horilla version 1.13.8, using settings 'horilla.settings'
Starting ASGI/Daphne version 4.2.1 development server at http://127.0.0.1:8000/
Quit the server with CTRL-BREAK.
```

Version comes from `horilla.__version__.__version__`.

### Implementation notes

- Patches Daphne’s `runserver` `Command.get_version` and wraps `stdout.write` to replace the `Django version ` prefix with `Horilla version `
- Does **not** add a custom management command or extra installed app

---

## Related

- [Utils index](./utils.md) — `horilla.utils` layout
- [Version helpers](./utils.md) — `horilla.utils.version` / `__version__` modules
- Project root `manage.py` — installs both helpers at startup
