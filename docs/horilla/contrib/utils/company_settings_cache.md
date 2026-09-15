# Per-company settings cache (`horilla.contrib.utils.company_settings_cache`)

## Purpose

Generic helpers so any app can cache a **company-scoped settings row** (or similar singleton) with Django’s cache framework. Used to avoid repeating the same DB lookup on every authenticated page render — especially from **context processors** and **menu `condition` callables**.

This module stays **app-agnostic**: it never hardcodes module names. Each caller owns its own `namespace` string (typically a model class attribute such as `CACHE_NAMESPACE`).

---

## API

| Helper | Role |
|--------|------|
| `company_setting_cache_key(namespace, company_id)` | Build cache key `horilla:company_setting:{namespace}:{company_id}` |
| `get_or_set_company_setting(namespace, company_id, fetch_fn, timeout=300)` | Return cached value; on miss call `fetch_fn()` and store it |
| `invalidate_company_setting(namespace, company_id)` | Delete the cache entry (call from `save` / `delete` / create paths) |

`DEFAULT_TIMEOUT` is **300** seconds (same window as the `company_list` context-processor cache).

```python
from horilla.contrib.utils.company_settings_cache import (
    get_or_set_company_setting,
    invalidate_company_setting,
)

setting = get_or_set_company_setting(
    MySettings.CACHE_NAMESPACE,
    company_id,
    lambda: MySettings.all_objects.filter(company_id=company_id).first(),
)
```

---

## Caller contract

1. Define a **namespace** on the model (e.g. `CACHE_NAMESPACE = "calendar.google_integration"`).
2. Read via `get_or_set_company_setting` (optionally keep a **request-local** L1 dict so the same request does not re-hit LocMem/Redis).
3. Call `invalidate_company_setting` after:
   - `save()` / `delete()`
   - `get_or_create` when a **new** row is created (clears a prior cached `None`)
   - `QuerySet.update` / `bulk_update` that changes the cached row without going through `save()`

---

## Current consumers

| Model / lookup | Namespace | Typical trigger |
|----------------|-----------|-----------------|
| `MultipleCurrency.get_default_currency` | `core.default_currency` | `currency_context` |
| `GoogleIntegrationSetting` | `calendar.google_integration` | My Settings menu condition |
| `MeetingIntegrationSetting` | `meeting.integration` | Menu conditions |
| `CallIntegrationSetting` | `calls.integration` | Menu conditions |
| `OpportunitySettings` | `opportunities.settings` | Opportunities menu / feature checks |

Namespaces live on each model — not in this util — so addon modules (e.g. CRM) can adopt the same helpers without coupling into `horilla.contrib.utils`.

---

## Related documentation

- Context processors: [../../context_processors.md](../../context_processors.md)
- Utils app overview: [utils.md](utils.md)
