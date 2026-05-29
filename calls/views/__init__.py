"""Views for the calls app, including call log management and integration settings."""

from calls.views.core import (
    CallIntegrationSettingsView,
    CallSettingsTabView,
    CallAccessControlTabContent,
    CallProvidersTabContent,
    CallAccessRolesView,
    CallAccessUsersView,
    CallAccessRolesDetailView,
    CallAccessUsersDetailView,
    CallUserSettingsView,
)

from calls.views.provider import (
    CallProviderListView,
    CallProviderFormView,
    CallProviderFieldsView,
    CallProviderDeleteView,
    CallProviderTestConnectionView,
    ProviderWebhookView,
    TwilioTwiMLView,
)

from calls.views.call_log import (
    CallLogNavView,
    CallLogView,
    CallLogListView,
    CallLogDeleteView,
    CallLogDetailView,
    ClickToCallView,
    ObjectCallLogView,
)

__all__ = [
    # Core Views
    "CallIntegrationSettingsView",
    "CallSettingsTabView",
    "CallAccessControlTabContent",
    "CallProvidersTabContent",
    "CallAccessRolesView",
    "CallAccessUsersView",
    "CallAccessRolesDetailView",
    "CallAccessUsersDetailView",
    "CallUserSettingsView",
    # Provider Views
    "CallProviderListView",
    "CallProviderFormView",
    "CallProviderFieldsView",
    "CallProviderDeleteView",
    "CallProviderTestConnectionView",
    "ProviderWebhookView",
    "TwilioTwiMLView",
    # Call Log Views
    "CallLogNavView",
    "CallLogView",
    "CallLogListView",
    "CallLogDeleteView",
    "CallLogDetailView",
    "ClickToCallView",
    "ObjectCallLogView",
]
