"""
Per-type tab list views for activities tied to a parent object
(Task, Meeting, Call, Email, Event).
"""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils.functional import cached_property  # type: ignore

from horilla.contrib.core.models import HorillaContentType
from horilla.contrib.generics.views import HorillaListView
from horilla.contrib.mail.models import HorillaMail
from horilla.urls import reverse_lazy
from horilla.utils.decorators import (
    htmx_required,
    method_decorator,
    permission_required_or_denied,
)
from horilla.utils.translation import gettext_lazy as _

from ...models import Activity
from .mixins import ActivityTabListMixin

_EDIT_ACTION = {
    "action": "Edit",
    "src": "assets/icons/edit.svg",
    "img_class": "w-4 h-4",
    "permission": "activity.change_activity",
    "own_permission": "activity.change_own_activity",
    "owner_field": ["owner", "assigned_to"],
    "attrs": """
                hx-get="{get_edit_url}?new=true"
                hx-target="#modalBox"
                hx-swap="innerHTML"
                onclick="openModal()"
                """,
}

_DELETE_ACTION = {
    "action": "Delete",
    "src": "assets/icons/a4.svg",
    "img_class": "w-4 h-4",
    "permission": "activity.delete_activity",
    "attrs": """
                hx-post="{get_delete_url}"
                hx-target="#deleteModeBox"
                hx-swap="innerHTML"
                hx-trigger="click"
                hx-vals='{{"check_dependencies": "true"}}'
                onclick="openDeleteModeModal()"
            """,
}

_TAB_ACTIONS = [_EDIT_ACTION, _DELETE_ACTION]
_CALL_TAB_ACTIONS = [_EDIT_ACTION, _DELETE_ACTION]


@method_decorator(htmx_required, name="dispatch")
@method_decorator(
    permission_required_or_denied(
        ["activity.view_activity", "activity.view_own_activity"]
    ),
    name="dispatch",
)
class TaskListView(ActivityTabListMixin, LoginRequiredMixin, HorillaListView):
    """Task List view."""

    model = Activity
    bulk_select_option = False
    paginate_by = 5
    table_width = False
    table_height_as_class = "h-[calc(_100vh_-_520px_)]"
    list_column_visibility = False
    _col_attrs_first_field = "title"
    actions = _TAB_ACTIONS

    columns = [
        ("Title", "title"),
        ("Due Date", "due_datetime"),
        ("Priority", "task_priority"),
        (_("Status"), "status_col"),
    ]

    def get_search_url(self):
        """Return the search URL for the task list scoped to this object."""
        return reverse_lazy(
            "activity:task_list", kwargs={"object_id": self.kwargs["object_id"]}
        )

    def get_main_url(self):
        """Return the main URL for the task list scoped to this object."""
        return reverse_lazy(
            "activity:task_list", kwargs={"object_id": self.kwargs["object_id"]}
        )

    @property
    def search_url(self):
        """Return the search URL property."""
        return self.get_search_url()

    @property
    def main_url(self):
        """Return the main URL property."""
        return self.get_main_url()

    def get_queryset(self):
        status_view_map = {
            "pending": "ActivityTaskListPending",
            "completed": "ActivityTaskListCompleted",
        }
        queryset = super().get_queryset()
        object_id = self.kwargs.get("object_id")
        view_type = self.request.GET.get("view_type", "pending")
        content_type_id = self.request.GET.get("content_type_id")

        if object_id and content_type_id:
            try:
                content_type = HorillaContentType.objects.get(id=content_type_id)
                queryset = queryset.filter(
                    object_id=object_id, content_type=content_type, activity_type="task"
                )
            except HorillaContentType.DoesNotExist:
                queryset = queryset.none()
        else:
            queryset = queryset.none()

        if view_type == "completed":
            queryset = queryset.filter(status="completed")
            self.view_id = status_view_map["completed"]
        elif view_type == "pending":
            queryset = queryset.exclude(status="completed")
            self.view_id = status_view_map["pending"]

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["object_id"] = self.kwargs.get("object_id")
        context["view_type"] = self.request.GET.get("view_type", "pending")
        return context


@method_decorator(htmx_required, name="dispatch")
@method_decorator(
    permission_required_or_denied(
        ["activity.view_activity", "activity.view_own_activity"]
    ),
    name="dispatch",
)
class MeetingListView(ActivityTabListMixin, HorillaListView):
    """Meeting list view."""

    model = Activity
    paginate_by = 10
    bulk_select_option = False
    table_width = False
    table_height_as_class = "h-[calc(_100vh_-_520px_)]"
    list_column_visibility = False
    _col_attrs_first_field = "title"
    actions = _TAB_ACTIONS

    columns = [
        ("Title", "title"),
        ("Start Date", "get_start_date"),
        ("End Date", "get_end_date"),
        (_("Meeting Link"), "meeting_link_col"),
        (_("Status"), "status_col"),
    ]

    def get_search_url(self):
        """Return the search URL for the meeting list scoped to this object."""
        return reverse_lazy(
            "activity:meeting_list", kwargs={"object_id": self.kwargs["object_id"]}
        )

    def get_main_url(self):
        """Return the main URL for the meeting list scoped to this object."""
        return reverse_lazy(
            "activity:meeting_list", kwargs={"object_id": self.kwargs["object_id"]}
        )

    @property
    def search_url(self):
        """Return the search URL property."""
        return self.get_search_url()

    @property
    def main_url(self):
        """Return the main URL property."""
        return self.get_main_url()

    def get_queryset(self):
        status_view_map = {
            "pending": "ActivityMeetingListPending",
            "completed": "ActivityMeetingListCompleted",
        }
        queryset = super().get_queryset()
        object_id = self.kwargs.get("object_id")
        view_type = self.request.GET.get("view_type", "pending")
        content_type_id = self.request.GET.get("content_type_id")

        if object_id and content_type_id:
            try:
                content_type = HorillaContentType.objects.get(id=content_type_id)
                queryset = queryset.filter(
                    object_id=object_id,
                    content_type=content_type,
                    activity_type="meeting",
                )
            except HorillaContentType.DoesNotExist:
                queryset = queryset.none()
        else:
            queryset = queryset.none()

        if view_type == "completed":
            queryset = queryset.filter(status="completed")
            self.view_id = status_view_map["completed"]
        elif view_type == "pending":
            queryset = queryset.exclude(status="completed")
            self.view_id = status_view_map["pending"]

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["object_id"] = self.kwargs.get("object_id")
        context["view_type"] = self.request.GET.get("view_type", "pending")
        return context


@method_decorator(htmx_required, name="dispatch")
@method_decorator(
    permission_required_or_denied(
        ["activity.view_activity", "activity.view_own_activity"]
    ),
    name="dispatch",
)
class CallListView(ActivityTabListMixin, HorillaListView):
    """List view for call activities."""

    model = Activity
    paginate_by = 10
    bulk_select_option = False
    table_height_as_class = "h-[calc(_100vh_-_520px_)]"
    table_width = False
    list_column_visibility = False
    _col_attrs_first_field = "call_purpose"
    actions = _CALL_TAB_ACTIONS

    columns = [
        ("Purpose", "call_purpose"),
        ("Type", "call_type"),
        ("Duration", "call_duration_display"),
        (_("Status"), "status_col"),
    ]

    def get_search_url(self):
        """Return the search URL for the call list scoped to this object."""
        return reverse_lazy(
            "activity:call_list", kwargs={"object_id": self.kwargs["object_id"]}
        )

    def get_main_url(self):
        """Return the main URL for the call list scoped to this object."""
        return reverse_lazy(
            "activity:call_list", kwargs={"object_id": self.kwargs["object_id"]}
        )

    @property
    def search_url(self):
        """Return the search URL property."""
        return self.get_search_url()

    @property
    def main_url(self):
        """Return the main URL property."""
        return self.get_main_url()

    def get_queryset(self):
        status_view_map = {
            "pending": "ActivityCallListPending",
            "completed": "ActivityCallListCompleted",
        }
        queryset = super().get_queryset()
        object_id = self.kwargs.get("object_id")
        view_type = self.request.GET.get("view_type", "pending")
        content_type_id = self.request.GET.get("content_type_id")

        if object_id and content_type_id:
            try:
                content_type = HorillaContentType.objects.get(id=content_type_id)
                queryset = queryset.filter(
                    object_id=object_id,
                    content_type=content_type,
                    activity_type="log_call",
                ).exclude(call_purpose="telephony")
            except HorillaContentType.DoesNotExist:
                queryset = queryset.none()
        else:
            queryset = queryset.none()

        if view_type == "completed":
            queryset = queryset.filter(status="completed")
            self.view_id = status_view_map["completed"]
        elif view_type == "pending":
            queryset = queryset.exclude(status="completed")
            self.view_id = status_view_map["pending"]

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["object_id"] = self.kwargs.get("object_id")
        context["view_type"] = self.request.GET.get("view_type", "pending")
        return context


@method_decorator(htmx_required, name="dispatch")
@method_decorator(
    permission_required_or_denied(
        [
            "mail.view_horillamail",
            "mail.view_own_horillamail",
            "mail.add_horillamail",
            "mail.add_own_horillamail",
        ]
    ),
    name="dispatch",
)
class EmailListView(HorillaListView):
    """List view for email activities."""

    model = HorillaMail
    bulk_select_option = False
    paginate_by = 10
    table_width = False
    table_height_as_class = "h-[calc(_100vh_-_520px_)]"
    list_column_visibility = False

    columns = [
        ("Subject", "render_subject"),
        ("Send To", "to"),
        ("Sent At", "sent_at"),
        ("Status", "get_mail_status_display"),
    ]

    def get_search_url(self):
        """Return the search URL for the email list scoped to this object."""
        return reverse_lazy(
            "activity:email_list", kwargs={"object_id": self.kwargs["object_id"]}
        )

    @property
    def search_url(self):
        """Return the search URL property."""
        return self.get_search_url()

    action_col = {
        "draft": [
            {
                "action": "Send Email",
                "src": "assets/icons/email_black.svg",
                "img_class": "w-4 h-4",
                "attrs": """
                            hx-get="{get_edit_url}"
                            hx-target="#horillaModalBox"
                            hx-swap="innerHTML"
                            onclick="openhorillaModal()"
                            """,
            },
            {
                "action": "Delete",
                "src": "assets/icons/a4.svg",
                "img_class": "w-4 h-4",
                "attrs": """
                        hx-post="{get_delete_url}?view=draft"
                        hx-target="#modalBox"
                        hx-swap="innerHTML"
                        hx-trigger="click"
                        hx-vals='{{"check_dependencies": "false"}}'
                        onclick="openModal()"
                    """,
            },
        ],
        "scheduled": [
            {
                "action": "Cancel",
                "src": "assets/icons/cancel.svg",
                "img_class": "w-4 h-4",
                "attrs": """
                        hx-get="{get_edit_url}?cancel=true"
                        hx-target="#horillaModalBox"
                        hx-swap="innerHTML"
                        hx-trigger="click"
                        onclick="openhorillaModal()"
                    """,
            },
            {
                "action": "Snooze",
                "src": "assets/icons/clock.svg",
                "img_class": "w-4 h-4",
                "attrs": """
                        hx-get="{get_reschedule_url}"
                        hx-target="#modalBox"
                        hx-swap="innerHTML"
                        hx-trigger="click"
                        onclick="openModal()"
                    """,
            },
            {
                "action": "Delete",
                "src": "assets/icons/a4.svg",
                "img_class": "w-4 h-4",
                "attrs": """
                        hx-post="{get_delete_url}?view=scheduled"
                        hx-target="#modalBox"
                        hx-swap="innerHTML"
                        hx-trigger="click"
                        hx-vals='{{"check_dependencies": "false"}}'
                        onclick="openModal()"
                    """,
            },
        ],
        "sent": [
            {
                "action": "View Email",
                "src": "assets/icons/eye1.svg",
                "img_class": "w-4 h-4",
                "attrs": """
                            hx-get="{get_view_url}"
                            hx-target="#contentModalBox"
                            hx-swap="innerHTML"
                            onclick="openContentModal()"
                            """,
            },
            {
                "action": "Delete",
                "src": "assets/icons/a4.svg",
                "img_class": "w-4 h-4",
                "attrs": """
                hx-post="{get_delete_url}?view=sent"
                hx-target="#modalBox"
                hx-swap="innerHTML"
                hx-trigger="click"
                hx-vals='{{"check_dependencies": "false"}}'
                onclick="openModal()"
            """,
            },
        ],
    }

    # Delivered / bounced / opened / failed share the same actions as "sent"
    action_col["delivered"] = action_col["sent"]
    action_col["bounced"] = action_col["sent"]
    action_col["opened"] = action_col["sent"]
    action_col["failed"] = action_col["sent"]

    @cached_property
    def actions(self):
        """Return the action set for the current email view_type (sent/draft/scheduled)."""
        view_type = self.request.GET.get("view_type")
        return self.action_col.get(view_type)

    def get_queryset(self):
        status_view_map = {
            "sent": "activity-email-list-sent",
            "draft": "activity-email-list-draft",
            "scheduled": "activity-email-list-scheduled",
        }
        sent_statuses = ["sent", "delivered", "bounced", "opened", "failed"]

        queryset = super().get_queryset()
        object_id = self.kwargs.get("object_id")
        view_type = self.request.GET.get("view_type", "sent")
        content_type_id = self.request.GET.get("content_type_id")

        if object_id and content_type_id:
            try:
                content_type = HorillaContentType.objects.get(id=content_type_id)
                queryset = queryset.filter(
                    object_id=object_id, content_type=content_type
                )
            except HorillaContentType.DoesNotExist:
                queryset = queryset.none()
        else:
            queryset = queryset.none()

        if view_type in status_view_map:
            if view_type == "sent":
                queryset = queryset.filter(mail_status__in=sent_statuses)
            else:
                queryset = queryset.filter(mail_status=view_type)
            self.view_id = status_view_map[view_type]

        user = self.request.user
        if not user.has_perm("mail.view_horillamail") and not user.has_perm(
            "mail.add_horillamail"
        ):
            queryset = queryset.filter(created_by=user)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["object_id"] = self.kwargs.get("object_id")
        context["view_type"] = self.request.GET.get("view_type", "sent")
        return context


@method_decorator(htmx_required, name="dispatch")
@method_decorator(
    permission_required_or_denied(
        ["activity.view_activity", "activity.view_own_activity"]
    ),
    name="dispatch",
)
class EventListView(ActivityTabListMixin, HorillaListView):
    """List view for event activities."""

    model = Activity
    bulk_select_option = False
    paginate_by = 10
    table_width = False
    table_height_as_class = "h-[calc(_100vh_-_520px_)]"
    list_column_visibility = False
    _col_attrs_first_field = "title"
    actions = _TAB_ACTIONS

    columns = [
        ("Title", "title"),
        ("Start Date", "get_start_date"),
        ("End Date", "get_end_date"),
        ("Location", "location"),
        (_("Status"), "status_col"),
    ]

    def get_search_url(self):
        """Return the search URL for the event list scoped to this object."""
        return reverse_lazy(
            "activity:event_list", kwargs={"object_id": self.kwargs["object_id"]}
        )

    @property
    def search_url(self):
        """Return the search URL property."""
        return self.get_search_url()

    def get_queryset(self):
        status_view_map = {
            "pending": "ActivityEventListPending",
            "completed": "ActivityEventListCompleted",
        }
        queryset = super().get_queryset()
        object_id = self.kwargs.get("object_id")
        view_type = self.request.GET.get("view_type", "pending")
        content_type_id = self.request.GET.get("content_type_id")

        if object_id and content_type_id:
            try:
                content_type = HorillaContentType.objects.get(id=content_type_id)
                queryset = queryset.filter(
                    object_id=object_id,
                    content_type=content_type,
                    activity_type="event",
                )
            except HorillaContentType.DoesNotExist:
                queryset = queryset.none()
        else:
            queryset = queryset.none()

        if view_type == "completed":
            queryset = queryset.filter(status="completed")
            self.view_id = status_view_map["completed"]
        elif view_type == "pending":
            queryset = queryset.exclude(status="completed")
            self.view_id = status_view_map["pending"]

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["object_id"] = self.kwargs.get("object_id")
        context["view_type"] = self.request.GET.get("view_type", "pending")
        return context
