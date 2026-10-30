"""
Views for Horilla Mail app.

This package provides mail form, recipients, preview, draft, delete and schedule views.
Submodules: base, form, recipients, preview_draft, delete_schedule.
"""

from horilla.contrib.mail.views.core.base import (
    extract_inline_images_with_cid,
    parse_email_pills_context,
)
from horilla.contrib.mail.views.core.schedule import (
    HorillaMailtDeleteView,
    ScheduleMailModallView,
    ScheduleMailView,
)
from horilla.contrib.mail.views.core.form import HorillaMailFormView
from horilla.contrib.mail.views.core.preview_draft import (
    CheckDraftChangesView,
    DiscardDraftView,
    HorillaMailPreviewView,
    SaveDraftView,
)
from horilla.contrib.mail.views.core.recipients import (
    AddEmailView,
    EmailSuggestionView,
    RemoveEmailView,
)
from horilla.contrib.mail.views.core.track import TrackOpenView

__all__ = [
    "parse_email_pills_context",
    "extract_inline_images_with_cid",
    "HorillaMailFormView",
    "AddEmailView",
    "RemoveEmailView",
    "EmailSuggestionView",
    "HorillaMailPreviewView",
    "CheckDraftChangesView",
    "SaveDraftView",
    "DiscardDraftView",
    "HorillaMailtDeleteView",
    "ScheduleMailView",
    "ScheduleMailModallView",
    "TrackOpenView",
]
