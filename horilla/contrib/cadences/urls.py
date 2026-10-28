"""
URLs for the cadences app
"""

# First party imports (Horilla)
from horilla.urls import path

# Local party imports
# Local imports
from . import views

app_name = "cadences"

urlpatterns = [
    path("cadence-view/", views.CadenceView.as_view(), name="cadence_view"),
    path("cadence-nav-view/", views.CadenceNavbar.as_view(), name="cadence_nav_view"),
    path(
        "cadence-list-view/", views.CadenceListView.as_view(), name="cadence_list_view"
    ),
    path(
        "cadence-create-view/",
        views.CadenceFormView.as_view(),
        name="cadence_create_view",
    ),
    path(
        "cadence-update-view/<int:pk>/",
        views.CadenceFormView.as_view(),
        name="cadence_update_view",
    ),
    path(
        "cadence-followup-create-view/<int:cadence_pk>/",
        views.CadenceFollowUpCreateView.as_view(),
        name="cadence_followup_create_view",
    ),
    path(
        "cadence-followup-update-view/<int:pk>/",
        views.CadenceFollowUpCreateView.as_view(),
        name="cadence_followup_update_view",
    ),
    path(
        "cadence-followup-delete-view/<int:pk>/",
        views.CadenceFollowUpDeleteView.as_view(),
        name="cadence_followup_delete_view",
    ),
    path(
        "cadence-followup-do-this-value-field/",
        views.CadenceFollowupDoThisValueFieldView.as_view(),
        name="cadence_followup_do_this_value_field",
    ),
    path(
        "cadence-activate/<int:pk>/",
        views.CadenceToggleView.as_view(),
        name="cadence_activate",
    ),
    path(
        "cadence-delete-view/<int:pk>/",
        views.CadenceDeleteView.as_view(),
        name="cadence_delete_view",
    ),
    path(
        "cadence-detail-view/<int:pk>/",
        views.CadenceDetailView.as_view(),
        name="cadence_detail_view",
    ),
    path(
        "cadence-detail-nav-view/",
        views.CadenceDetailNavbar.as_view(),
        name="cadence_detail_nav_view",
    ),
    path(
        "cadence-enroll/<str:app_label>/<str:record_model>/<int:record_pk>/",
        views.CadenceEnrollView.as_view(),
        name="cadence_enroll_modal",
    ),
    path(
        "cadence-unenroll/<int:pk>/",
        views.CadenceUnenrollView.as_view(),
        name="cadence_unenroll_view",
    ),
    path(
        "cadence-report-view/",
        views.CadenceReportView.as_view(),
        name="cadence_report_view",
    ),
    path(
        "cadence-report-tab-view/",
        views.CadenceReportTabView.as_view(),
        name="cadence_report_tab_view",
    ),
    path(
        "cadence-task-tab-view/",
        views.CadenceTaskTabView.as_view(),
        name="cadence_task_tab_view",
    ),
    path(
        "cadence-task-list-view/",
        views.CadenceTaskListView.as_view(),
        name="cadence_task_list_view",
    ),
    path(
        "cadence-call-tab-view/",
        views.CadenceCallTabView.as_view(),
        name="cadence_call_tab_view",
    ),
    path(
        "cadence-call-list-view/",
        views.CadenceCallListView.as_view(),
        name="cadence_call_list_view",
    ),
    path(
        "cadence-email-tab-view/",
        views.CadenceEmailTabView.as_view(),
        name="cadence_email_tab_view",
    ),
    path(
        "cadence-email-list-view/",
        views.CadenceEmailListView.as_view(),
        name="cadence_email_list_view",
    ),
]
