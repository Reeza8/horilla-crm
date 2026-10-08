"""
Detail-view extensions for reviews: when an edit made from a record's detail
view moves the record into pending review, warn the user and send them back to
the list (the record is hidden from module lists while its review is pending).

Only edits that actually start or reopen a review warn; edits to other fields
leave the detail view untouched. Covers the "Edit Details" bulk save
(``UpdateAllFieldsView``) and the stage/pipeline bar
(``HorillaDetailView.update_pipeline``).
"""

# Standard library imports
from urllib.parse import parse_qs, urlencode, urlparse

# Third-party imports (Django)
from django.contrib import messages

# First party imports (Horilla)
from horilla.apps import apps
from horilla.contrib.utils.methods import get_section_info_for_model
from horilla.extension.mixin import MixinExtension
from horilla.extension.view import ViewExtension
from horilla.utils.translation import gettext_lazy as _
from horilla.web import HttpResponse

# Local imports
from .utils import was_moved_to_pending_review


def _is_current_page(request, url):
    """True if ``url`` is the page the edit was made from (the detail view)."""
    current = request.headers.get("HX-Current-URL") or ""
    return bool(url) and urlparse(str(url)).path == urlparse(current).path


def _get_list_redirect_url(request, model, pk):
    """
    List page to send the user back to after the record moved into review.

    Tries the list crumb saved when the detail view was opened, then the stored
    referer, then the model's own list/section page. Anything that is the
    detail page itself is skipped, otherwise the user would stay where they are.
    """
    model_name = model._meta.model_name
    candidates = []
    crumbs = request.session.get(f"detail_view_breadcrumbs_{model_name}_{pk}") or []
    if len(crumbs) > 1:
        candidates.append(crumbs[0][1])
    candidates.append(request.session.get(f"detail_referer_{model_name}_{pk}"))
    try:
        section_url = get_section_info_for_model(model).get("url")
        section = parse_qs(
            urlparse(request.headers.get("HX-Current-URL") or "").query
        ).get("section")
        if section_url and section and "section=" not in section_url:
            joiner = "&" if "?" in section_url else "?"
            section_url = f"{section_url}{joiner}{urlencode({'section': section[0]})}"
        candidates.append(section_url)
    except Exception:
        pass
    for url in candidates:
        if url and url != "#" and not _is_current_page(request, url):
            return str(url)
    return "/"


def _warn_and_redirect(request, model, pk):
    messages.warning(
        request,
        str(
            _(
                "This record has been moved to a pending review request and "
                "is hidden from the list until it is approved."
            )
        ),
    )
    response = HttpResponse()
    response["HX-Redirect"] = _get_list_redirect_url(request, model, pk)
    return response


class ReviewBulkEditExtension(ViewExtension):
    """Warn and return to the list after an "Edit Details" save starts a review."""

    _inherit_view = (
        "horilla.contrib.generics.views.helpers.edit_field.UpdateAllFieldsView"
    )

    def post(self, request, pk, app_label, model_name):
        """Redirect after a successful save that moved the record into review."""
        response = super().post(request, pk, app_label, model_name)
        if response.status_code == 200 and was_moved_to_pending_review(
            request, app_label, model_name, pk
        ):
            return _warn_and_redirect(
                request, apps.get_model(app_label, model_name), pk
            )
        return response


class ReviewPipelineUpdateExtension(MixinExtension):
    """Warn and return to the list after a stage change starts a review."""

    _inherit_mixin = "horilla.contrib.generics.views.details.HorillaDetailView"

    def update_pipeline(self, original, request, *args, **kwargs):
        """Redirect after a pipeline update that moved the record into review."""
        response = original(request, *args, **kwargs)
        record = getattr(self, "object", None)
        if (
            record is not None
            and response.status_code == 200
            and was_moved_to_pending_review(
                request, record._meta.app_label, record._meta.model_name, record.pk
            )
        ):
            return _warn_and_redirect(request, record.__class__, record.pk)
        return response
