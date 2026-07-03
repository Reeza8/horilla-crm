"""Module containing package metadata used by Horilla (version, name, icons)."""

from django.utils.translation import gettext_lazy as _

__version__ = "1.12.4"
__module_name__ = _("Core System")
__release_date__ = ""
__description__ = _(
    "Core system providing authentication, configuration, utilities, and platform-level services."
)
__icon__ = "assets/icons/logo.png"

__1_12_4__ = _(
    "Core: added get_allowed_user_ids() for subordinate-aware ownership and fixed "
    "sync_role_permissions_on_role_change to assign role permissions to new users via "
    "transaction.on_commit. Generics: unified record-level access with check_record_access(), "
    "check_record_change_access(), and check_record_delete_access(); extended view_own "
    "filtering to global search, detail tabs, mail compose and drafts, notes and attachments, "
    "related lists, and activity sections. Parent-record change and delete access now gates tab "
    "actions, add buttons, and col_attr row links; callable action labels, icons, and hidden_if "
    "supported in render_action_button. HorillaModelForm skips ownership filtering when the user "
    "has global view permission. Fixed HorillaSingleDeleteView model resolution, "
    "ColumnSelectionForm self.data access, sanitize_html font-colour passthrough, and "
    "related-list add-column permission and URL handling."
)

__1_12_3__ = _(
    "Redesigned sidebar to a fixed-width icon-nav with text labels and corrected the "
    "sub-sidebar toggle button position when collapsed. Extension framework: renamed "
    "model _inherit to _inherit_model across metaclass, registry, and migration ops. "
    "Core: auto-sync user permissions when a role changes via signals; filter "
    "allowed_users by active company in OwnerQuerysetMixin. Generics: fixed Add Column "
    "to List in tabbed list views."
)

__1_12_2__ = _(
    "Added IP-based brute-force lockout on login and uniform forgot-password responses to "
    "prevent user enumeration. Fixed local settings to apply after app extensions. "
    "Generics: fixed filter-panel toggle in tabbed views with duplicate element IDs; "
    "sanitized notes-and-attachments fields against XSS and updated delete-button styling "
    "with themed icons. Menu: improved sub-sidebar active-link detection and unique item IDs."
)

__1_12_1__ = _(
    "Extension tests now use contrib.core examples instead of CRM-specific modules. Added "
    "centralized sanitize_html and sanitize_plain_text helpers with bleach CSS allowlisting, "
    "Summernote DOMPurify mirroring, CSV/XLSX cell sanitization against formula injection, "
    "and notification template XSS sanitization with validation-error field clearing. Fixed "
    "generics Select2 edit-mode FK filtering by loading parent instances via all_objects and "
    "scoping request.active_company to the record tenant; fixed navbar search losing focus by "
    "removing hx-select-oob/hx-preserve. Core: restricted login history to the current user, "
    "improved role empty state, refined User and RegionalFormatting forms, showed company on "
    "ChangeUserCompanyForm, debounced saveActiveTab for SQLite, and rendered readable user-agent "
    "details in login history. Registered static, i18n, and horilla_tags as template builtins."
)

__1_12_0__ = _(
    "Expanded extension framework with _inherit_form, _inherit_list, _inherit_card, "
    "_inherit_filter, _inherit_nav, _inherit_kanban, and _inherit_detail composition with "
    "caching and per-request resolution. Introduced PhoneWidget and PhoneField for "
    "international phone numbers. Fixed generics bulk-delete Prefetch slicing, action button "
    "text wrapping, and HolidayForm user-selection defaults. Centralized horilla.db "
    "transaction and connection imports and standardized first-party import groups."
)

__1_11_1__ = _(
    "Custom CSRF failure view and csrf_failure.html for DEBUG=False. CSRF protection "
    "restored on state-mutating stage and calendar-preference views. FiscalYear, "
    'RegionalFormatting, Company, and User forms switched to fields="__all__" with '
    "field_order and keep_on_form so HorillaModelForm base fields are no longer dropped, "
    "with sensitive user fields excluded. Business Hour add-button hides without reload, "
    "and BusinessHourHolidayModalView is guarded for deleted records. Generics skip M2M "
    "relations in bulk-delete to avoid ProtectedError and add cursor-pointer to note, "
    "attachment, and related-list actions. Added horilla.utils.timezone and "
    "horilla.db.models.signals shims, standardized first-party import groups, and broad "
    "docstring coverage for pylint compliance."
)

__1_11_0__ = _(
    "Workflow automation engine (rules, conditions, actions, Celery time triggers, "
    "execution history). Public booking platform with slots, public pages, reminders, "
    "and booking/activity integration. ERP-style _inherit model extensions with "
    "InjectField and extension-owned migrations. ShiftHour scheduling and BusinessHour "
    "enhancements with holiday support. HTMX-first UX, multi-step form refactors, "
    "django-countries subdivisions, permission inheritance fixes, activity/booking mail "
    "templates, and Django 6.0 generics stability improvements."
)

__1_10_1__ = _(
    "Meeting Integration contrib app (Zoom/Teams OAuth, meeting links, activity hooks). "
    "Generics export and JSONField display improvements. My Profile panel scrolls within "
    "a fixed viewport. Calendar Google settings respect active company on POST. "
    "Scheduled automations use corrected Celery task paths."
)

__1_10_0__ = _(
    "Major platform 1.10 layout: support apps consolidated under the contrib namespace with "
    "short Django app labels (activity, core, mail, theme, and related modules). "
    "AppLauncher configs, imports, URL namespaces, static paths, and permission "
    "or content-type strings updated to match the new labels. "
    "Added sync tooling to align migration records, content types, audit "
    "log references, and related data when upgrading existing databases."
)


__1_9_0__ = _(
    "Added Google Calendar integration with sync, service, and settings support. "
    "Implemented cadence signals for runtime activities. Centralized HorillaView "
    "layout resolution with get_layout_url() for backend-driven layout selection."
)


__1_8_1__ = _(
    "Switched Channels backend from InMemoryChannelLayer to RedisChannelLayer. "
    "Moved Holiday model to dedicated holidays.py. Improved branch list layout, "
    "business hour and holiday bulk select, and viewport-based table heights. "
    "Added SECURITY.md documentation."
)


__1_8_0__ = _(
    "Introduced unified Process Builder system combining reviews and approvals. "
    "Added async notification and mail handling with background thread execution. "
    "Improved health check endpoint and version changelog modal system. "
    "Updated assign_first_company_to_all_users signal to use User model directly."
)


__1_7_0__ = _(
    "Strengthened core validation with strict enforcement of include_models during "
    "feature registration, validation of subsection-to-section mappings, and export "
    "of StreamingHttpResponse via Horilla HTTP utilities."
)


__1_6_0__ = _(
    "Added health check endpoint, synced fiscal year and period logic, "
    "improved version changelog modal system, and switched Django Channels "
    "backend to Redis for better performance and reliability."
)


__1_5_0__ = _(
    "Improved global search model registry loading, standardized error handling "
    "with dedicated 403, 404, 405, and 500 templates, strengthened authentication "
    "flow using Django authenticate(), and applied multiple security and "
    "stability improvements across internal views."
)


__1_4_0__ = _(
    "Introduced the Horilla AppLauncher system for dynamic application "
    "registration. Added horilla.shortcuts, horilla.urls, and horilla.utils "
    "utilities. Refactored project URL handling and improved internal "
    "framework architecture for modular applications."
)


__1_2_0__ = _(
    "Improved system configuration handling, strengthened dashboard layout "
    "validation, enhanced filter processing reliability, and added multiple "
    "defensive validation improvements across core components."
)


__1_1_0__ = _(
    "Added an 'All Companies' option to the company dropdown, allowing users "
    "to view data irrespective of company selection."
)
