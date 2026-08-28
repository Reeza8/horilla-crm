"""
init file for leads models
"""

# Local imports
from horilla_crm.leads.models.base import (
    DEFAULT_LEAD_INIT_STAGES,
    LeadStatus,
    Lead,
    EmailToLeadConfig,
    LeadCaptureForm,
)


from horilla_crm.leads.models.assignment_rules import (
    LeadAssignmentRule,
    LeadAssignmentCondition,
    LeadAssignmentMatchCriteria,
)

__all__ = [
    # Base models
    "DEFAULT_LEAD_INIT_STAGES",
    "LeadStatus",
    "Lead",
    "EmailToLeadConfig",
    "LeadCaptureForm",
    # Assignment rule models
    "LeadAssignmentRule",
    "LeadAssignmentCondition",
    "LeadAssignmentMatchCriteria",
]
