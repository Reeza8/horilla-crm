"""CRM module version information."""

from horilla.utils.translation import gettext_lazy as _

__version__ = "1.11.5"
__module_name__ = "CRM"
__release_date__ = ""
__description__ = _("CRM module for managing leads, contacts, and opportunities.")
__icon__ = "assets/icons/icon2.svg"

__1_11_5__ = _(
    "Accounts: corrected lead_source choice key from social media to social_media. "
    "Replaced direct owner checks with subordinate-aware get_allowed_user_ids() filtering "
    "across accounts, contacts, leads, and opportunities related lists and campaign actions. "
    "Moved CRM form permission guards from get() to has_permission() with "
    "check_record_change_access and check_record_delete_access on parent records. "
    "Hierarchy modals now traverse to the root ancestor and highlight the active node for "
    "campaigns, accounts, and contacts. Added circular parent-child validation on Contact, "
    "Account, and Campaign. Forecast: fixed cached_property misuse in type-tab views. "
    "Fixed account hierarchy view_own permission check."
)

__1_11_4__ = _(
    "Contacts: initialize account before conditional relation lookup on model save. "
    "Forecast: avoid constant-test checks when reading cached company access in "
    "forecast-type tab views."
)

__1_11_3__ = _(
    "Forecast: excluded currency and current_amount from ForecastTargetForm; fixed "
    "active-tab detection and wrapped opportunity-type labels with i18n; refactored "
    "forecast-type table period-cell layout and sticky-column sizing; reduced N+1 "
    "queries and cached repeated fiscal-year checks. Normalized contact fixture country "
    "values to ISO 3166-1 alpha-2 codes."
)

__1_11_2__ = _(
    "Refactored leads core views into tab sub-packages and opportunities split and stages "
    "views into sub-packages. Standardized first-party import section headers and migrated "
    "transaction imports to horilla.db. Leads: fixed Go to Leads navigation from convert "
    "success modal; enhanced web-to-lead form with Select2 and improved styling. "
    "Opportunities: fixed team selling and split checks via _resolve_company and all_objects "
    "OpportunitySettings lookups; scoped OpportunityTeamForm user choices to active company."
)

__1_11_1__ = _(
    "Lead and opportunity stage saving now validates first and uses update-or-create "
    "instead of delete-and-recreate, so stages still referenced by leads or opportunities "
    "are no longer deleted (preventing ProtectedError on the PROTECT FKs). CSRF protection "
    "restored on stage-group and custom-stage views with csrf_token added to the HTMX "
    "forms. Fixed KeyError on multi-step create forms by removing direct created_by / "
    "updated_by access stripped by HorillaMultiStepForm. Removed redundant fields "
    "attributes superseded by form_class on forecast, assignment-rule, opportunity-team, "
    "and scoring-rule single-form views, plus docstring coverage for pylint compliance."
)

__1_10_0__ = _(
    "Aligned with platform 1.10: imports and integrations target contrib packages "
    "and short Django app labels (core, generics, mail, activity, and other shared modules). "
    "URL namespaces, static paths, permission strings, and ForeignKey string references "
    "updated where they cross into contrib apps; the CRM module keeps its original app label "
    "and database table prefix."
)

__1_4_0__ = _(
    "Enhanced CRM fixtures with additional fields. Improved UI refinements "
    "including navbar z-index fixes, KPI color consistency, and standardized "
    "template formatting across leads, accounts, campaigns, contacts, "
    "and opportunities modules."
)

__1_3_0__ = _(
    "Introduced advanced CRM visualization capabilities including chart views, "
    "timeline (Gantt-style) views, split layout navigation, and card-based record "
    "views. Improved pipeline data exploration and navigation across Leads, "
    "Accounts, Campaigns, Contacts, and Opportunities."
)

__1_2_0__ = _(
    "Enabled advanced quick filters, improved column selector behavior, "
    "refined CRM list view consistency, and enhanced filtering reliability "
    "across Leads, Accounts, Contacts, Campaigns, and Opportunities."
)

__1_1_0__ = _(
    "Migrated CRM sub-apps to Horilla AppLauncher and replaced Django utilities "
    "with horilla.utils.decorators, horilla.utils.translation, and horilla.shortcuts "
    "where applicable."
)
