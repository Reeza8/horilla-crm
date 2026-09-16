"""Shared helpers for building public-facing absolute URLs."""

from django.conf import settings


def build_absolute_url(path, request=None):
    """Build an absolute public-facing URL for the given path.

    Prefers settings.SITE_URL (the admin-configured public HTTPS URL) so
    links keep working when the request arrives via a proxy that doesn't
    report the public scheme/host, and when there is no request at all
    (e.g. links sent from Celery tasks). Falls back to
    request.build_absolute_uri() when SITE_URL isn't configured, and to
    the raw path if neither is available.
    """
    site_url = getattr(settings, "SITE_URL", "").rstrip("/")
    if site_url:
        return f"{site_url}{path}"
    if request:
        return request.build_absolute_uri(path)
    return path
