"""
Feature registration for Approvals app.

This declares the "approvals" feature and its registry key ("approval_models"),
so other apps can opt-in their models without modifying their model code.
"""

# First party imports (Horilla)
from horilla.registry.feature import register_feature, register_model_for_feature

register_feature(
    "approvals",
    "approval_models",
    auto_register_all=False,
)

register_model_for_feature(
    app_label="approvals",
    model_name="ApprovalInstance",
    features=["export_data"],
)
