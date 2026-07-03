"""Version information for the horilla.contrib.activity module."""

from horilla.utils.translation import gettext_lazy as _

__version__ = "1.11.5"
__module_name__ = "Activity"
__release_date__ = ""
__description__ = _(
    "Module for tracking and managing activities such as tasks,calls, events, and emails."
)
__icon__ = "activity/assets/icons/activity-red.svg"

__1_11_5__ = _(
    "Simplified mail visibility so can_send_mail and can_view_mail follow parent-record "
    "change and view access. Activity tab Edit/Delete actions and email Send/Cancel/Snooze "
    "actions are gated on parent-record change/delete access with subordinate-aware "
    "ownership via get_allowed_user_ids()."
)

__1_11_4__ = _(
    "Constrained activity tab list table height for consistent scrolling. Added "
    "cursor-pointer to Pending and Completed Calls sub-tabs."
)

__1_11_3__ = _(
    "Disabled base owner_filtration on EmailListView. Centralised get_main_url in the "
    "list-view mixin and fixed tab-calls typo in status update and activity tab template. "
    "Task and activity creates now navigate directly to the correct tab instead of "
    "reverting to the first tab after reload; aligned task-create reload trigger with "
    "project-wide jQuery convention. Fixed delete and bulk-action views that reverted "
    "to the wrong tab."
)

__1_11_2__ = _(
    "Fixed call duration field ordering and removed redundant validation; history tab now "
    "correctly identifies CallLog entries and displays call status. Use load_branding() TITLE "
    "as the fallback company name in meeting invitation emails. Allow ActivityView for users "
    "with view_own_activity as well as view_activity. Added meeting provider choices (Zoom, "
    "Google Meet, Microsoft Teams) on the Activity model."
)

__1_11_1__ = _(
    "Email-tab permissions corrected to add/view/change/delete own-record checks. "
    "Removed redundant fields attributes from create-view forms superseded by form_class. "
    "Adopted the horilla.utils.timezone shim, standardized first-party imports, and added "
    "class and method docstrings for pylint compliance."
)

__1_10_2__ = _(
    "Activity forms aligned with HorillaModelForm layout: field_order, "
    'Meta.fields = "__all__", and Meta.exclude; save logic and HTMX behavior unchanged.'
)

__1_10_1__ = _(
    "Meeting integration in activities: schedule meetings from activities, send invites "
    "and reminders, and display generated Zoom/Teams meeting links on activity records."
)

__1_10_0__ = _(
    "Release 1.10: activity ships under contrib with app label activity. "
    "AppLauncher, imports, namespaces, registrations, templates, and metadata "
    "references updated from the legacy activity package name to the contrib layout."
)

__1_2_1__ = _(
    "Reduced redundant history entries, improved Many-to-Many field representation, "
    "and added cleaner labels for mail events and activity creation with "
    "new template filters for better rendering."
)

__1_2_0__ = _(
    "Improved activity workflow behavior. The Pending tab now shows all incomplete activities"
    "regardless of status label, and activity type configuration handling was enhanced "
    "for improved workflow accuracy."
)


__1_1_0__ = _(
    "Migrated from Django AppConfig to Horilla AppLauncher and replaced Django utilities with"
    "horilla.utils.decorators, horilla.utils.translation, and horilla.shortcuts where applicable."
)
