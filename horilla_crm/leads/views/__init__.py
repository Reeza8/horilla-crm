"""Aggregate view modules for the `leads.views` package."""

# Local imports
from horilla_crm.leads.views.core import (
    LeadView,
    LeadNavbar,
    LeadListView,
    LeadCardView,
    LeadDetailView,
    LeadGroupByView,
    LeadChartView,
    LeadKanbanView,
    LeadSplitView,
    LeadTimelineView,
)
from horilla_crm.leads.views.lead_stage import (
    LeadsStageView,
    LeadStageNavbar,
    LeadStageListView,
    ChangeFinalStage,
    CreateLeadStage,
    ToggleOrderFieldView,
    LeadStatusDeleteView,
    UpdateLeadStageOrderView,
    LoadLeadStagesView,
    CustomStagesFormView,
    SaveCustomStagesView,
    AddStageView,
    RemoveStageView,
    CreateStageGroupView,
    InitializeDatabaseLeadStages,
)
from horilla_crm.leads.views.mail_to_lead import (
    MailToLeadView,
    MailToLeadNavbar,
    MailToLeadListView,
    MailToLeadFormView,
    EmailToLeadConfigDeleteView,
)
from horilla_crm.leads.views.web_to_lead import (
    LeadFormBuilderView,
    UpdateFormHeadingView,
    UpdateFormPreviewView,
    SaveLeadFormView,
    AddFieldView,
    RemoveFieldView,
    PublicLeadFormView,
    ToggleReturnUrlView,
)
from horilla_crm.leads.views.lead_actions import (
    LeadDeleteView,
    LeadFormView,
    LeadsSingleFormView,
    LeadChangeOwnerForm,
)
from horilla_crm.leads.views.lead_conversion import LeadConversionView
from horilla_crm.leads.views.lead_link_records import LeadLinkRecordsView
from horilla_crm.leads.views.lead_link_from_record import (
    ContactLinkLeadsView,
    ConvertedLeadSelect2View,
    OpportunityLinkLeadsView,
)
from horilla_crm.leads.views.assignment_rule_form import LeadAssignmentOwnerView
from horilla_crm.leads.views.assignment_rule import (
    LeadsAssignmentView,
    LeadAssignmentNavbar,
    LeadAssignmentListView,
    LeadAssignmentActivateView,
    LeadAssignmentForm,
    LeadAssignmentDelete,
    AssignmentRuleDetailView,
    AssignmentRuleDetailNavbar,
    AssignmentConditionFormView,
    AssignmentConditionDeleteView,
    ToggleAssignToFieldView,
    ToggleNotifyMethodFieldView,
)
from horilla_crm.leads.views.detail_tabs import (
    LeadsDetailTab,
    LeadsDetailViewTabView,
    LeadsActivityTabView,
    LeadRelatedLists,
    LeadsHistoryTabView,
    LeadsNotesAndAttachments,
)

__all__ = [
    "LeadAssignmentOwnerView",
    # Core Views
    "LeadView",
    "LeadNavbar",
    "LeadListView",
    "LeadCardView",
    "LeadDetailView",
    "LeadGroupByView",
    "LeadChartView",
    "LeadKanbanView",
    "LeadSplitView",
    "LeadTimelineView",
    # Lead Stage Views
    "LeadsStageView",
    "LeadStageNavbar",
    "LeadStageListView",
    "ChangeFinalStage",
    "CreateLeadStage",
    "ToggleOrderFieldView",
    "LeadStatusDeleteView",
    "UpdateLeadStageOrderView",
    "LoadLeadStagesView",
    "CustomStagesFormView",
    "SaveCustomStagesView",
    "AddStageView",
    "RemoveStageView",
    "CreateStageGroupView",
    "InitializeDatabaseLeadStages",
    # Mail to Lead Views
    "MailToLeadView",
    "MailToLeadNavbar",
    "MailToLeadListView",
    "MailToLeadFormView",
    "EmailToLeadConfigDeleteView",
    # Web to Lead Views
    "LeadFormBuilderView",
    "UpdateFormHeadingView",
    "UpdateFormPreviewView",
    "SaveLeadFormView",
    "AddFieldView",
    "RemoveFieldView",
    "PublicLeadFormView",
    "ToggleReturnUrlView",
    # Lead Actions Views
    "LeadDeleteView",
    "LeadFormView",
    "LeadsSingleFormView",
    "LeadChangeOwnerForm",
    # Lead Conversion Views
    "LeadConversionView",
    "LeadLinkRecordsView",
    "ContactLinkLeadsView",
    "ConvertedLeadSelect2View",
    "OpportunityLinkLeadsView",
    # Assignment Rule Views
    "LeadsAssignmentView",
    "LeadAssignmentNavbar",
    "LeadAssignmentListView",
    "LeadAssignmentActivateView",
    "LeadAssignmentForm",
    "LeadAssignmentDelete",
    "AssignmentRuleDetailView",
    "AssignmentRuleDetailNavbar",
    "AssignmentConditionFormView",
    "AssignmentConditionDeleteView",
    "ToggleAssignToFieldView",
    "ToggleNotifyMethodFieldView",
    # Detail Tabs Views
    "LeadsDetailTab",
    "LeadsDetailViewTabView",
    "LeadsActivityTabView",
    "LeadRelatedLists",
    "LeadsHistoryTabView",
    "LeadsNotesAndAttachments",
]
