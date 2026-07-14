"""
HTTP response classes for Horilla.

Provides redirect, refresh, and script responses with safe URL validation
and optional HTMX (HX-Redirect, HX-Refresh) support.
"""

from django.contrib import messages
from django.http import HttpResponse, HttpResponseRedirect

from horilla.shortcuts import render
from horilla.utils.translation import gettext_lazy as _

from .url_safety import safe_url


class HttpNotFound(Exception):
    """Custom 404 exception that renders a Horilla-specific error template."""

    def __init__(
        self,
        message=_(
            "The page you are looking for does not exist or may have been moved."
        ),
        context=None,
        template=None,
    ):
        """
        Initialize the HttpNotFound exception.

        Args:
            message (str): The error message to display.
            context (dict, optional): Additional context variables for the template.
            template (str, optional): Path to the error template.
        """
        self.message = message
        self.context = context or {}
        self.template = template or "404.html"
        super().__init__(message)

    def as_response(self, request):
        """
        Render the exception as an HTTP 404 response.

        Args:
            request (HttpRequest): The request that triggered the exception.

        Returns:
            HttpResponse: A rendered 404 response.
        """
        return render(
            request,
            self.template,
            {**self.context, "error_message": self.message},
            status=404,
        )


class RedirectResponse(HttpResponseRedirect):
    """
    Safe redirect class to prevent open redirect vulnerabilities.
    Validates the target URL before redirecting.
    """

    def __init__(self, request, redirect_to=None, message=None, fallback_url="/"):
        """
        Initialize a safe redirect response.

        :param request: Django request object.
        :param redirect_to: Target URL (optional). If omitted, uses HTTP_REFERER.
        :param message: Optional error message to add via Django messages.
        :param fallback_url: Safe fallback URL if redirect_to is invalid (default: "/").
        """

        # If redirect_to not provided, use HTTP_REFERER
        previous_url = redirect_to or request.META.get("HTTP_REFERER", fallback_url)

        if message:
            messages.error(request, message)

        previous_url = safe_url(request, previous_url, fallback_url)

        if request.headers.get("HX-Request"):
            super().__init__(previous_url)
            self.status_code = 200
            self.headers.pop("Location", None)
            self.headers["HX-Redirect"] = previous_url
        else:
            super().__init__(previous_url)


class RefreshResponse(HttpResponse):
    """
    HTTP response that triggers a full page refresh in HTMX clients.
    For HTMX requests: sets HX-Refresh header to reload the current page.
    For non-HTMX requests: falls back to a standard redirect to the current path.
    """

    def __init__(self, request=None, fallback_url="/") -> None:
        super().__init__(content=b"", content_type="text/plain")
        if request and not request.headers.get("HX-Request"):
            safe_path = safe_url(request, request.path, fallback_url)
            self.status_code = 302
            self["Location"] = safe_path
        else:
            self.status_code = 200
            self["HX-Refresh"] = "true"


class ScriptResponse(HttpResponse):
    """
    HTTP response that returns a ``<script>`` payload for HTMX UI actions.

    Replaces ad-hoc script strings such as::

        HttpResponse(
            "<script>htmx.trigger('#tab-contact_relationships-btn','click');"
            "closeModal();</script>"
        )

    with a typed API. **Keyword argument order is preserved** — script parts are
    emitted in the same order you pass the flags::

        # htmx.trigger first, then closeModal
        ScriptResponse(
            extra="htmx.trigger('#tab-contact_relationships-btn','click');",
            close=True,
        )

        # closeModal first, then reload list
        ScriptResponse(close=True, reload=True)

        ScriptResponse(reload=True, msgs=True, close=True)

    Built-in actions:

    - ``reload`` → ``$('#reloadButton').click();``
    - ``msgs`` → ``$('#reloadMessagesButton').click();``
    - ``close`` → ``closeModal();``
    - ``extra`` → custom JS (string or sequence of strings)
    """

    _ACTION_SCRIPTS = {
        "reload": "$('#reloadButton').click();",
        "msgs": "$('#reloadMessagesButton').click();",
        "close": "closeModal();",
    }

    def __init__(self, status: int = 200, **actions) -> None:
        content = self.build_script(**actions)
        super().__init__(content=content, content_type="text/html; charset=utf-8")
        self.status_code = status

    @staticmethod
    def _normalize_extra(
        extra: str | list[str] | tuple[str, ...] | None,
    ) -> list[str]:
        """Normalize extra into a list of JS statements."""
        if not extra:
            return []
        if isinstance(extra, str):
            chunks = [extra]
        else:
            chunks = list(extra)

        normalized = []
        for chunk in chunks:
            if chunk is None:
                continue
            statement = str(chunk).strip()
            if not statement:
                continue
            if statement.startswith("<script>") and statement.endswith("</script>"):
                statement = statement[len("<script>") : -len("</script>")].strip()
            if statement and not statement.endswith(";"):
                statement = f"{statement};"
            if statement:
                normalized.append(statement)
        return normalized

    @classmethod
    def build_script(cls, **actions) -> str:
        """
        Build the ``<script>...</script>`` body.

        Actions are appended in the order of the keyword arguments passed.
        Unknown action names raise ``TypeError``.
        """
        parts: list[str] = []
        for key, value in actions.items():
            if key in ("extra", "extra_script"):
                parts.extend(cls._normalize_extra(value))
                continue
            if key not in cls._ACTION_SCRIPTS:
                raise TypeError(
                    f"Unexpected ScriptResponse action {key!r}. "
                    f"Expected one of: {', '.join((*cls._ACTION_SCRIPTS, 'extra'))}."
                )
            if value:
                parts.append(cls._ACTION_SCRIPTS[key])
        return f"<script>{''.join(parts)}</script>"
