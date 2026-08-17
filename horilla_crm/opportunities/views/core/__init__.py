"""
Opportunity core views package.

Submodules: base (list, navbar, kanban, group_by, delete), forms, detail, detail_sections.
"""

# Local imports
from horilla_crm.opportunities.views.core.base import (
    OpportunityChartView,
    OpportunityDeleteView,
    OpportunityGroupByView,
    OpportunityKanbanView,
    OpportunityListView,
    OpportunityNavbar,
    OpportunitySplitView,
    OpportunityTimelineView,
    OpportunityView,
    OpportunityCardView,
)
from horilla_crm.opportunities.views.core.detail import (
    OpportunityActivityTabView,
    OpportunityDetailTab,
    OpportunityDetailView,
    OpportunityDetailViewTabView,
    OpportunityHistoryTabView,
    OpportunitiesNotesAndAttachments,
)
from horilla_crm.opportunities.views.core.detail_sections import (
    OpportunityContactRoleDeleteView,
    OpportunityContactRoleFormview,
    OpportunityRelatedLists,
    SelectClosedStageView,
)
from horilla_crm.opportunities.views.core.forms import (
    OpportunityChangeOwnerForm,
    OpportunityMultiStepFormView,
    OpportunitySingleFormView,
    RelatedOpportunityFormView,
    RelatedOpportunitySingleFormView,
    StageProbabilityFieldView,
)

__all__ = [
    "OpportunityView",
    "OpportunityNavbar",
    "OpportunityListView",
    "OpportunityDeleteView",
    "OpportunityKanbanView",
    "OpportunityCardView",
    "OpportunityGroupByView",
    "OpportunitySplitView",
    "OpportunityChartView",
    "OpportunityTimelineView",
    "OpportunityMultiStepFormView",
    "OpportunitySingleFormView",
    "RelatedOpportunityFormView",
    "RelatedOpportunitySingleFormView",
    "StageProbabilityFieldView",
    "OpportunityChangeOwnerForm",
    "OpportunityDetailView",
    "OpportunityDetailViewTabView",
    "OpportunityDetailTab",
    "OpportunityActivityTabView",
    "OpportunitiesNotesAndAttachments",
    "OpportunityHistoryTabView",
    "OpportunityRelatedLists",
    "OpportunityContactRoleFormview",
    "OpportunityContactRoleDeleteView",
    "SelectClosedStageView",
]
