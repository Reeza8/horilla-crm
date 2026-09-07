"""
URLs for the duplicates app
"""

# First party imports (Horilla)
from horilla.urls import path

# Local imports
from . import views

app_name = "duplicates"

urlpatterns = [
    # Main views
    path(
        "matching-rules/",
        views.MatchingRuleView.as_view(),
        name="matching_rule_view",
    ),
    path(
        "duplicate-rules/",
        views.DuplicateRuleView.as_view(),
        name="duplicate_rule_view",
    ),
    # Matching Rules URLs
    path(
        "matching-rules/nav/",
        views.MatchingRuleNavView.as_view(),
        name="matching_rule_nav_view",
    ),
    path(
        "matching-rules/list/",
        views.MatchingRuleListView.as_view(),
        name="matching_rule_list_view",
    ),
    path(
        "matching-rules/create/",
        views.MatchingRuleFormView.as_view(),
        name="matching_rule_create_view",
    ),
    path(
        "matching-rules/update/<int:pk>/",
        views.MatchingRuleFormView.as_view(),
        name="matching_rule_update_view",
    ),
    path(
        "matching-rules/delete/<int:pk>/",
        views.MatchingRuleDeleteView.as_view(),
        name="matching_rule_delete_view",
    ),
    # Duplicate Rules URLs
    path(
        "duplicate-rules/nav/",
        views.DuplicateRuleNavView.as_view(),
        name="duplicate_rule_nav_view",
    ),
    path(
        "duplicate-rules/list/",
        views.DuplicateRuleListView.as_view(),
        name="duplicate_rule_list_view",
    ),
    path(
        "duplicate-rules/create/",
        views.DuplicateRuleFormView.as_view(),
        name="duplicate_rule_create_view",
    ),
    path(
        "duplicate-rules/update/<int:pk>/",
        views.DuplicateRuleFormView.as_view(),
        name="duplicate_rule_update_view",
    ),
    path(
        "duplicate-rules/toggle/<int:pk>/",
        views.DuplicateRuleToggleView.as_view(),
        name="duplicate_rule_toggle_view",
    ),
    path(
        "duplicate-rules/delete/<int:pk>/",
        views.DuplicateRuleDeleteView.as_view(),
        name="duplicate_rule_delete_view",
    ),
    path(
        "duplicate-rules/detail/<int:pk>/",
        views.DuplicateRuleDetailView.as_view(),
        name="duplicate_rule_detail_view",
    ),
    # AJAX/HTMX views
    path(
        "matching-rule-choices/",
        views.MatchingRuleCriteriaFieldChoicesView.as_view(),
        name="matching_rule_choices_view",
    ),
    path(
        "duplicate-warning-modal/<str:session_key>/",
        views.DuplicateWarningModalView.as_view(),
        name="duplicate_warning_modal",
    ),
    path(
        "generic-detail/<int:content_type_id>/<int:pk>/",
        views.GenericDuplicateDetailView.as_view(),
        name="generic_duplicate_detail_view",
    ),
    path(
        "potential-duplicates-tab/",
        views.PotentialDuplicatesTabView.as_view(),
        name="potential_duplicates_tab",
    ),
    path(
        "merge-duplicates-compare/",
        views.MergeDuplicatesCompareView.as_view(),
        name="merge_duplicates_compare",
    ),
    path(
        "merge-duplicates-summary/",
        views.MergeDuplicatesSummaryView.as_view(),
        name="merge_duplicates_summary",
    ),
    path(
        "merge-duplicates/",
        views.MergeDuplicatesView.as_view(),
        name="merge_duplicates",
    ),
]
