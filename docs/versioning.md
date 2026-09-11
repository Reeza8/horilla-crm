# Horilla CRM versioning

Source of truth for humans and AI assistants that update `__version__.py` files.

Related: [CHANGELOG.md](../CHANGELOG.md) · collection UI: `horilla/utils/version.py`

---

## Rule 1 — Platform version = whole CRM product (not the `horilla/` folder)

**`horilla/__version__.py` is the Horilla CRM product / platform version for the entire project.**

It is **not** “the version of code only under the `horilla/` directory.”

It drives:

- Git tag (e.g. `1.14.0`)
- Docker tag (`horilla/horilla-crm:1.14.0`)
- Product “About / Modules & Versions” core release
- The **product** changelog story for that release

So when deciding the platform bump and writing `__1_14_0__` (etc.), include
**project-wide** highlights: new top-level apps (`custom_fields/`, `booking/`,
`calls/`, …), `horilla_crm/`, contrib apps, and shared platform work.

### Do not under-weight (common AI mistake)

**Do not under-weight** that `horilla/__version__.py` is the whole CRM product version.

Wrong mental model:

- “Only files under `horilla/` count for platform `1.x.y`”
- “Custom Fields lives in `custom_fields/`, so platform stays a patch”
- “Weekly = always patch (`1.13.8` → `1.13.9`) even if a headline app shipped”

Correct mental model:

- Platform version = **entire CRM release**
- A headline feature anywhere in the repo (e.g. Custom Fields) can justify a
  **minor** platform bump (`1.13.8` → `1.14.0`)
- That module still keeps **its own** `__version__.py` line (e.g. `custom_fields` `1.0.0`)

---

## Rule 2 — Two independent version lines

| File | Versions | Bump from |
|------|----------|-----------|
| `horilla/__version__.py` | **Whole CRM product / platform** | Platform line only |
| Every other `**/__version__.py` | **That module only** | That file’s current `__version__` |

**Never** set mail/CRM/booking/custom_fields versions equal to the platform number.

Example for one week:

| File | Old → new | Why |
|------|-----------|-----|
| `horilla/__version__.py` | `1.13.8` → `1.14.0` | Product release; Custom Fields is the headline |
| `custom_fields/__version__.py` | `1.0.0` (first ship) | Module’s own line |
| `horilla_crm/__version__.py` | `1.11.14` → `1.11.15` | CRM-only commits |
| `horilla/contrib/mail/__version__.py` | `1.11.9` → `1.11.10` | Mail-only commits |

---

## Rule 3 — Platform semver (patch vs minor vs major)

| Bump | When |
|------|------|
| **Patch** (`1.13.8` → `1.13.9`) | Fixes, hardening, small UX; **no** headline product story |
| **Minor** (`1.13.8` → `1.14.0`) | Headline capability for the **product** (new app users care about, release-theme feature) |
| **Major** (`2.0.0`) | Breaking upgrades / incompatible remapping |

**Minor examples:** Custom Fields on Leads/Opportunities (forms, lists, filters, exports); Modules enablement UX; a new extension API marketed as the release theme.

**Patch examples:** crash fixes; HTMX guards; API tenant hardening on existing endpoints; runserver progress bar; icon-only polish.

---

## Rule 4 — Per-module `__version__.py` updates

1. Use git commits in the date range; bump only **substantive code** changes.
2. Skip docs-only, i18n-only, pylint/docstring-only, redundant `{% load %}` unless behavior changed.
3. Next version = **next patch** from that module’s current value (unless that module itself ships a real minor).
4. Add changelog **above** older entries: `1.11.15` → `__1_11_15__ = _("...")`.
5. Module changelog = **that app’s** commits only.
6. **Do not edit or remove** older `__X_Y_Z__` entries.
7. Leave `__release_date__` as-is unless the project already sets it.
8. Match existing file style (`gettext_lazy`, metadata fields).

Typical paths: `horilla/__version__.py` (product), `horilla/contrib/*/__version__.py`,
`horilla_crm/__version__.py`, `booking/`, `calls/`, `custom_fields/`, `horilla_jalali/`, …

---

## Rule 5 — Weekly update checklist (AI / maintainers)

1. `git log --since="START" --until="END+1day" --no-merges` (and per-app paths).
2. Decide platform **patch vs minor** using Rules 1 and 3 — **do not under-weight**
   features outside the `horilla/` folder.
3. Update `horilla/__version__.py` + `__X_Y_Z__` with **project-wide** highlights.
4. Patch-bump each impacted module from **its own** last version + module changelog.
5. Leave unchanged modules alone.
6. Summary table: App | Old | New | Changelog key | Reason.
7. Do not commit unless asked.

---

## `CHANGELOG.md`

Tracks the **same product numbers** as `horilla/__version__.py`. Per-app versions
are not listed there; they show in Modules & Versions via `horilla.utils.version`.
