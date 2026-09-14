"""
Generic per-company settings cache helpers.

Any app can cache a company-scoped singleton (or similar) settings row
by passing its own ``namespace`` string. Invalidate on save / delete
(and M2M changes when relevant) via ``invalidate_company_setting``.
"""

from django.core.cache import cache

# Match company_list context-processor timeout.
DEFAULT_TIMEOUT = 300


def company_setting_cache_key(namespace, company_id):
    """Return the cache key for a company-scoped settings row."""
    return f"horilla:company_setting:{namespace}:{company_id}"


def get_or_set_company_setting(
    namespace, company_id, fetch_fn, timeout=DEFAULT_TIMEOUT
):
    """
    Return the settings object for ``company_id``, loading via ``fetch_fn``
    only on cache miss.

    ``namespace`` is owned by the calling app (do not hardcode app names here).
    ``fetch_fn`` must be a zero-arg callable that returns the model instance
    or ``None``.
    """
    if not company_id:
        return None
    return cache.get_or_set(
        company_setting_cache_key(namespace, company_id),
        fetch_fn,
        timeout=timeout,
    )


def invalidate_company_setting(namespace, company_id):
    """Drop the cached settings row for ``company_id`` (no-op if missing)."""
    if not company_id:
        return
    cache.delete(company_setting_cache_key(namespace, company_id))
