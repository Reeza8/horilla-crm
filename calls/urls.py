"""URL configuration for the Horilla Calls Integration app."""

# First party imports (Horilla)
from horilla.urls import path

# Local imports
from . import views

app_name = "calls"

urlpatterns = [
    # Admin integration settings (Settings → Integrations)
    path(
        "settings/",
        views.CallIntegrationSettingsView.as_view(),
        name="integration_settings",
    ),

    # Per-user settings (My Settings → Calls)
    path(
        "user-settings/",
        views.CallUserSettingsView.as_view(),
        name="user_settings",
    ),

    # Access control modals (edit)
    path(
        "call-access-roles/",
        views.CallAccessRolesView.as_view(),
        name="call_access_roles",
    ),
    path(
        "call-access-users/",
        views.CallAccessUsersView.as_view(),
        name="call_access_users",
    ),
    # Access control detail (read-only list)
    path(
        "call-access-roles-detail/",
        views.CallAccessRolesDetailView.as_view(),
        name="call_access_roles_detail",
    ),
    path(
        "call-access-users-detail/",
        views.CallAccessUsersDetailView.as_view(),
        name="call_access_users_detail",
    ),

    # Provider management
    path(
        "provider-list/",
        views.CallProviderListView.as_view(),
        name="provider_list",
    ),
    path(
        "provider-create/",
        views.CallProviderFormView.as_view(),
        name="provider_create",
    ),
    path(
        "provider-update/<int:pk>/",
        views.CallProviderFormView.as_view(),
        name="provider_update",
    ),
    path(
        "provider-delete/<int:pk>/",
        views.CallProviderDeleteView.as_view(),
        name="provider_delete",
    ),
    path(
        "provider-test/<int:pk>/",
        views.CallProviderTestConnectionView.as_view(),
        name="provider_test",
    ),

    # Agent mappings
    path(
        "agent-list/",
        views.AgentMappingListView.as_view(),
        name="agent_list",
    ),
    path(
        "agent-create/",
        views.AgentMappingFormView.as_view(),
        name="agent_create",
    ),
    path(
        "agent-update/<int:pk>/",
        views.AgentMappingFormView.as_view(),
        name="agent_update",
    ),
    path(
        "agent-delete/<int:pk>/",
        views.AgentMappingDeleteView.as_view(),
        name="agent_delete",
    ),

    # Call logs
    path(
        "call-log-view/",
        views.CallLogView.as_view(),
        name="call_log_view",
    ),
    path(
        "call-log-nav/",
        views.CallLogNavView.as_view(),
        name="call_log_nav",
    ),
    path(
        "call-log-list/",
        views.CallLogListView.as_view(),
        name="call_log_list",
    ),
    path(
        "call-log-detail/<int:pk>/",
        views.CallLogDetailView.as_view(),
        name="call_log_detail",
    ),
    path(
        "call-log-delete/<int:pk>/",
        views.CallLogDeleteView.as_view(),
        name="call_log_delete",
    ),

    # Click-to-call
    path(
        "click-to-call/",
        views.ClickToCallView.as_view(),
        name="click_to_call",
    ),

    # Twilio TwiML endpoint — returns <Dial> XML to bridge outbound calls
    path(
        "twilio/twiml/<int:provider_pk>/",
        views.TwilioTwiMLView.as_view(),
        name="twilio_twiml",
    ),

    # Webhooks (csrf_exempt, no authentication)
    path(
        "webhook/<str:provider_type>/<int:provider_pk>/",
        views.ProviderWebhookView.as_view(),
        name="provider_webhook",
    ),
]
