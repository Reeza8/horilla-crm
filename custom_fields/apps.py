from horilla.apps import AppLauncher


class CustomFieldsConfig(AppLauncher):
    default = True
    default_auto_field = "django.db.models.BigAutoField"
    name = "custom_fields"
    verbose_name = "Custom Fields"

    url_prefix = "custom-fields/"
    url_module = "custom_fields.urls"
    url_namespace = "custom_fields"
    auto_import_modules = ["menu"]

    def ready(self):
        super().ready()
        self._patch_lead_forms()
        self._patch_opportunity_forms()

    def _patch_lead_forms(self):
        """Inject CustomField mixins into Lead form and view classes."""
        try:
            from custom_fields.integration import (
                CustomFieldMultiStepMixin,
                CustomFieldSingleFormMixin,
                CustomFieldViewMixin,
            )
            from horilla_crm.leads.forms import LeadFormClass, LeadSingleForm
            from horilla_crm.leads.views.lead_actions import (
                LeadFormView,
                LeadsSingleFormView,
            )

            _inject_mixin(LeadFormClass, CustomFieldMultiStepMixin)
            _inject_mixin(LeadSingleForm, CustomFieldSingleFormMixin)
            _inject_mixin(LeadFormView, CustomFieldViewMixin)
            _inject_mixin(LeadsSingleFormView, CustomFieldViewMixin)
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning(
                "custom_fields: could not patch Lead forms: %s", exc
            )

    def _patch_opportunity_forms(self):
        """Inject CustomField mixins into Opportunity form and view classes."""
        try:
            from custom_fields.integration import (
                CustomFieldMultiStepMixin,
                CustomFieldSingleFormMixin,
                CustomFieldViewMixin,
            )
            from horilla_crm.opportunities.forms import (
                OpportunityFormClass,
                OpportunitySingleForm,
            )
            from horilla_crm.opportunities.views.core.forms import (
                OpportunityMultiStepFormView,
                OpportunitySingleFormView,
            )

            _inject_mixin(OpportunityFormClass, CustomFieldMultiStepMixin)
            _inject_mixin(OpportunitySingleForm, CustomFieldSingleFormMixin)
            _inject_mixin(OpportunityMultiStepFormView, CustomFieldViewMixin)
            _inject_mixin(OpportunitySingleFormView, CustomFieldViewMixin)
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning(
                "custom_fields: could not patch Opportunity forms: %s", exc
            )


def _inject_mixin(target_class, mixin_class):
    """
    Prepend mixin_class to target_class.__bases__ if not already there.
    This is safe to do once in AppConfig.ready().
    """
    if mixin_class in target_class.__mro__:
        return
    target_class.__bases__ = (mixin_class,) + target_class.__bases__
