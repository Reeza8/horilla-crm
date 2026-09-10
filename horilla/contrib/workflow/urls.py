"""
URLs for the workflow app
"""

# First party imports (Horilla)
from horilla.urls import path

# Local imports
from . import views

app_name = "workflow"

urlpatterns = [
    path(
        "workflow-rule-view/",
        views.WorkflowRuleView.as_view(),
        name="workflow_rule_view",
    ),
    path(
        "workflow-rule-navbar-view/",
        views.WorkflowRuleNavbar.as_view(),
        name="workflow_rule_nav_view",
    ),
    path(
        "workflow-rule-list-view/",
        views.WorkflowRuleListView.as_view(),
        name="workflow_rule_list_view",
    ),
    path(
        "workfow-activate-toggle/<int:pk>/",
        views.WorkflowActiveToggleView.as_view(),
        name="workflow_rule_activate_toggle_view",
    ),
    path(
        "workflow-rule-create-view/",
        views.WorkflowCreateUpdateView.as_view(),
        name="workflow_rule_create_view",
    ),
    path(
        "workflow-rule-update-view/<int:pk>/",
        views.WorkflowCreateUpdateView.as_view(),
        name="workflow_rule_update_view",
    ),
    path(
        "workflow-rule-delete-view/<int:pk>/",
        views.WorkflowDeleteView.as_view(),
        name="workflow_rule_delete_view",
    ),
    path(
        "workflow-rule-detail-view/<int:pk>/",
        views.WorkflowRuleDetailView.as_view(),
        name="workflow_rule_detail_view",
    ),
    path(
        "workflow-rule-detail-navbar/",
        views.WorkflowRuleDetailNavbar.as_view(),
        name="workflow_rule_detail_navbar",
    ),
    # Actions
    path(
        "workflow-action-fields/",
        views.WorkflowActionFieldsView.as_view(),
        name="workflow_action_fields_view",
    ),
    path(
        "workflow-action-value-widget/",
        views.WorkflowActionValueWidgetView.as_view(),
        name="workflow_action_value_widget_view",
    ),
    path(
        "workflow-action-add/<int:rule_pk>/",
        views.WorkflowActionSaveView.as_view(),
        name="workflow_action_add_view",
    ),
    path(
        "workflow-action-edit/<int:pk>/",
        views.WorkflowActionSaveView.as_view(),
        name="workflow_action_edit_view",
    ),
    path(
        "workflow-action-delete/<int:pk>/",
        views.WorkflowActionDeleteView.as_view(),
        name="workflow_action_delete_view",
    ),
    # Time-trigger actions
    path(
        "workflow-time-trigger-add/<int:rule_pk>/",
        views.WorkflowTimeTriggerSaveView.as_view(),
        name="workflow_time_trigger_add_view",
    ),
    path(
        "workflow-time-trigger-edit/<int:pk>/",
        views.WorkflowTimeTriggerSaveView.as_view(),
        name="workflow_time_trigger_edit_view",
    ),
    path(
        "workflow-time-trigger-delete/<int:pk>/",
        views.WorkflowTimeTriggerDeleteView.as_view(),
        name="workflow_time_trigger_delete_view",
    ),
    path(
        "workflow-time-trigger-history/<int:rule_pk>/",
        views.WorkflowTimeTriggerHistoryView.as_view(),
        name="workflow_time_trigger_history_view",
    ),
]
