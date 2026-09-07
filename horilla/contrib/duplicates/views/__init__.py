"""
Re-export duplicates views for `horilla.contrib.duplicates.views` imports.

This follows the same pattern as other apps (e.g. `core.views`):
small modules per view-group + a static aggregator here.
"""

from .matching_rules import (
    MatchingRuleView,
    MatchingRuleNavView,
    MatchingRuleListView,
    MatchingRuleFormView,
    MatchingRuleDeleteView,
    MatchingRuleCriteriaFieldChoicesView,
)
from .duplicate_rules import (
    DuplicateRuleView,
    DuplicateRuleNavView,
    DuplicateRuleListView,
    DuplicateRuleFormView,
    DuplicateRuleToggleView,
    DuplicateRuleDeleteView,
    DuplicateRuleDetailView,
)
from .merge import (
    GenericDuplicateDetailView,
    DuplicateWarningModalView,
    PotentialDuplicatesTabView,
    MergeDuplicatesCompareView,
    MergeDuplicatesSummaryView,
    MergeDuplicatesView,
)

__all__ = [
    # Matching rules
    "MatchingRuleView",
    "MatchingRuleNavView",
    "MatchingRuleListView",
    "MatchingRuleFormView",
    "MatchingRuleDeleteView",
    "MatchingRuleCriteriaFieldChoicesView",
    # Duplicate rules
    "DuplicateRuleView",
    "DuplicateRuleNavView",
    "DuplicateRuleListView",
    "DuplicateRuleFormView",
    "DuplicateRuleToggleView",
    "DuplicateRuleDeleteView",
    "DuplicateRuleDetailView",
    # Merge / generic / ajax-ish
    "GenericDuplicateDetailView",
    "DuplicateWarningModalView",
    "PotentialDuplicatesTabView",
    "MergeDuplicatesCompareView",
    "MergeDuplicatesSummaryView",
    "MergeDuplicatesView",
]
