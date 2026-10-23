"""
Horilla authentication mixins.

Provides mixins for Django views to handle authentication and authorization.
"""

from urllib.parse import urlparse

from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin as DjangoLoginRequiredMixin
from django.contrib.auth.views import redirect_to_login

from horilla.web import HttpResponse, safe_url

__all__ = [
    "LoginRequiredMixin",
    "login_redirect",
]


def _is_htmx(request):
    return bool(
        request.headers.get("HX-Request") or request.META.get("HTTP_HX_REQUEST")
    )


def _next_path(request):
    """Return the page the user was on (path + query) as a safe local URL."""
    candidates = (
        request.headers.get("HX-Current-URL") if _is_htmx(request) else None,
        request.headers.get("Referer") if _is_htmx(request) else None,
        request.get_full_path(),
    )
    for candidate in candidates:
        if not candidate:
            continue
        parsed = urlparse(candidate)
        path = parsed.path + (f"?{parsed.query}" if parsed.query else "")
        if path and safe_url(request, path, fallback=None):
            return path
    return request.get_full_path()


def login_redirect(request, login_url=None, redirect_field_name="next"):
    """
    Send a signed-out user to the login page.

    Normal requests get a 302. HTMX requests get a 204 with ``HX-Redirect`` so
    the browser navigates instead of swapping the login HTML into a fragment.
    """
    login_url = str(login_url or settings.LOGIN_URL)
    if not _is_htmx(request):
        return redirect_to_login(
            request.get_full_path(), login_url, redirect_field_name
        )
    response = HttpResponse(status=204)
    response["HX-Redirect"] = redirect_to_login(
        _next_path(request), login_url, redirect_field_name
    )["Location"]
    return response


class LoginRequiredMixin(DjangoLoginRequiredMixin):
    """Django's LoginRequiredMixin with an HTMX-aware login redirect."""

    def handle_no_permission(self):
        if not self.raise_exception and not self.request.user.is_authenticated:
            return login_redirect(
                self.request,
                login_url=self.get_login_url(),
                redirect_field_name=self.get_redirect_field_name(),
            )
        return super().handle_no_permission()
