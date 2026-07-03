"""Aggregate view modules for the  package."""

from horilla.contrib.mail.views.core import *
from horilla.contrib.mail.views.mail_template import (
    MailTemplateView,
    MailTemplateNavbar,
    MailTemplateListView,
    MailTemplateCreateUpdateView,
    MailTemplatePreviewView,
    TemplateContentView,
    MailTemplateSelectView,
    SaveAsMailTemplateView,
    MailTemplateDeleteView,
    MailTemplateDetailView,
)
from horilla.contrib.mail.views.outlook import (
    OutlookMailServerFormView,
    OutlookLoginView,
    OutlookCallbackView,
    refresh_outlook_token,
    OutlookRefreshTokenView,
)
from horilla.contrib.mail.views.incoming_mail import (
    IncomingMailServerView,
    IncomingMailServerNavbar,
    IncomingMailServerTypeSelectionView,
    IncomingMailServerListView,
    IncomingMailServerFormView,
)
from horilla.contrib.mail.views.outgoing_mail import (
    MailServerView,
    MailServerNavbar,
    MailServerTypeSelectionView,
    MailServerListView,
    OutgoingMailServerFormView,
    MailServerTestEmailView,
    MailServerDeleteView,
)
from horilla.contrib.mail.views.mail_config_detail import MailConfigDetailView
from horilla.contrib.mail.views.mail_history import (
    MailHistoryView,
    MailHistoryNavbar,
    MailHistoryListView,
)

__all__ = [
    # Mail template views
    "MailTemplateView",
    "MailTemplateNavbar",
    "MailTemplateListView",
    "MailTemplateCreateUpdateView",
    "MailTemplatePreviewView",
    "TemplateContentView",
    "MailTemplateSelectView",
    "SaveAsMailTemplateView",
    "MailTemplateDeleteView",
    "MailTemplateDetailView",
    # Outlook views
    "OutlookMailServerFormView",
    "OutlookLoginView",
    "OutlookCallbackView",
    "refresh_outlook_token",
    "OutlookRefreshTokenView",
    # Incoming mail server views
    "IncomingMailServerView",
    "IncomingMailServerNavbar",
    "IncomingMailServerTypeSelectionView",
    "IncomingMailServerListView",
    "IncomingMailServerFormView",
    # Outgoing mail views
    "MailServerView",
    "MailServerNavbar",
    "MailServerTypeSelectionView",
    "MailServerListView",
    "OutgoingMailServerFormView",
    "MailServerTestEmailView",
    "MailServerDeleteView",
    # Mail config detail view
    "MailConfigDetailView",
    # Mail history views
    "MailHistoryView",
    "MailHistoryNavbar",
    "MailHistoryListView",
]
