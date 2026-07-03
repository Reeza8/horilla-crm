"""
Views for the Activity module in the Horilla platform.
"""

# Standard library imports
from urllib.parse import urlencode

# Third-party imports (Django)
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils.functional import cached_property  # type: ignore
from django.views import View
from django.views.generic import DetailView

from horilla.contrib.core.models import HorillaContentType
from horilla.contrib.generics.mixins import RecentlyViewedMixin
from horilla.contrib.generics.views import (
    HorillaDetailSectionView,
    HorillaDetailTabView,
    HorillaDetailView,
    HorillaHistorySectionView,
    HorillaKanbanView,
    HorillaNavView,
    HorillaNotesAttachementSectionView,
    HorillaSingleDeleteView,
    HorillaTabView,
    HorillaView,
)
from horilla.contrib.generics.views.details import (
    check_record_access,
    check_record_change_access,
    check_record_delete_access,
)
from horilla.shortcuts import render

# First-party imports (Horilla)
from horilla.urls import reverse_lazy
from horilla.utils.decorators import (
    htmx_required,
    method_decorator,
    permission_required,
    permission_required_or_denied,
)
from horilla.utils.translation import gettext_lazy as _
from horilla.web import HttpResponse, RefreshResponse

from ..filters import ActivityFilter
from ..models import Activity
from .list_view import AllActivityListView

# One source of truth — mark each field with where it should appear
ACTIVITY_TYPE_SPECIFIC_FIELDS = {
    "meeting": [
        ("title", "both"),
        ("start_datetime", "both"),
        ("end_datetime", "both"),
        ("is_all_day", "tab"),
        ("is_online", "tab"),
        ("location", "tab"),
        ("meeting_host", "tab"),
        ("participants", "tab"),
        ("meeting_provider", "tab"),
        ("meeting_url", "tab"),
        ("reminder", "tab"),
        ("external_participants", "tab"),
    ],
    "event": [
        ("title", "both"),
        ("start_datetime", "both"),
        ("end_datetime", "both"),
        ("location", "tab"),
        ("is_all_day", "tab"),
        ("participants", "tab"),
    ],
    "task": [
        ("owner", "both"),
        ("task_priority", "both"),
        ("due_datetime", "both"),
        ("assigned_to", "tab"),
    ],
    "log_call": [
        ("call_duration_display", "both"),
        ("call_duration_seconds", "both"),
        ("call_type", "tab"),
        ("call_purpose", "tab"),
        ("notes", "tab"),
    ],
}

COMMON_FIELDS = [
    "subject",
    "activity_type",
    "status",
    "description",
    "related_object",
]


def get_fields_for(activity_type, view="both"):
    """
    view="summary" → only fields marked "summary" or "both"
    view="tab"     → only fields marked "tab" or "both"
    """
    fields = ACTIVITY_TYPE_SPECIFIC_FIELDS.get(activity_type, [])
    return [field for field, scope in fields if scope in (view, "both")]


def get_activity_detail_view_fields(activity_type):
    """
    Return the activity detail view fields
    """
    return [
        "subject",
        "activity_type",
        "status",
        "assigned_to",
        *get_fields_for(activity_type, view="summary"),  # only "summary" + "both"
    ]


def get_activity_detail_tab_fields(activity_type):
    """
    Return the activity detail tab fields
    """
    return [
        "activity_type",
        "subject",
        "status",
        "description",
        "assigned_to",
        *get_fields_for(activity_type, view="tab"),  # "tab" + "both"
    ]


@method_decorator(htmx_required, name="dispatch")
class HorillaActivitySectionView(DetailView):
    """
    Generic Activity Tab View
    """

    template_name = "activity_tab.html"
    context_object_name = "obj"

    def dispatch(self, request, *args, **kwargs):
        """Dispatch the request; verify record access then handle errors with HX-Refresh."""
        try:
            self.object = self.get_object()
        except Exception as e:
            messages.error(self.request, e)
            return RefreshResponse(self.request)
        if not check_record_access(request.user, self.object):
            return render(request, "403.html", status=403)
        return super().dispatch(request, *args, **kwargs)

    def add_task_button(self):
        """Return button configuration for creating a new task."""
        return {
            "url": f"""{reverse_lazy("activity:task_create_form")}""",
            "attrs": 'id="task-create"',
        }

    def add_meetings_button(self):
        """Return button configuration for creating a new meeting."""
        return {
            "url": f"""{reverse_lazy("activity:meeting_create_form")}""",
            "attrs": 'id="meeting-create"',
        }

    def add_call_button(self):
        """Return button configuration for creating a new call log."""
        return {
            "url": f"""{reverse_lazy("activity:call_create_form")}""",
            "attrs": 'id="call-create"',
        }

    def add_email_button(self):
        """Return button configuration for sending an email."""
        return {
            "url": f"""{reverse_lazy("mail:send_mail_view")}""",
            "attrs": 'id="email-create"',
            "title": _("Send Email"),
        }

    def add_event_button(self):
        """Return button configuration for creating a new event."""
        return {
            "url": f"""{reverse_lazy("activity:event_create_form")}""",
            "attrs": 'id="event-create"',
        }

    def get_context_data(self, **kwargs):
        """Add activity tab context: object_id, content_type, and action buttons."""
        context = super().get_context_data(**kwargs)
        pk = self.kwargs.get("pk")
        context["object_id"] = pk
        context["model_name"] = self.model._meta.model_name
        context["app_label"] = self.model._meta.app_label
        content_type = HorillaContentType.objects.get_for_model(self.model)
        context["content_type_id"] = content_type.id
        context["add_task_button"] = self.add_task_button() or {}
        context["add_meetings_button"] = self.add_meetings_button() or {}
        context["add_call_button"] = self.add_call_button() or {}
        context["add_email_button"] = self.add_email_button() or {}
        context["add_event_button"] = self.add_event_button() or {}
        user = self.request.user

        can_view_record = check_record_access(user, self.object)
        can_change_record = check_record_change_access(user, self.object)

        can_send_mail = can_change_record
        context["can_send_mail"] = can_send_mail

        can_view_mail = can_view_record
        context["can_view_mail"] = can_view_mail

        # Add buttons are shown when the user can change the parent record
        context["can_add_as_owner"] = can_change_record
        return context


@method_decorator(htmx_required, name="dispatch")
@method_decorator(
    permission_required_or_denied(
        ["activity.view_activity", "activity.view_own_activity"]
    ),
    name="dispatch",
)
class AllActivityTabbedView(LoginRequiredMixin, HorillaTabView):
    """
    Tabbed list view that separates activities by type.
    Each tab shows its own HorillaListView with type-specific columns.
    """

    template_name = "activity_type_tab_view.html"
    view_id = "activity-type-tabs"
    tab_class = "h-[calc(_100vh_-_260px_)] overflow-hidden"

    tabs = [
        {
            "id": "tasks",
            "title": _("Tasks"),
            "url": reverse_lazy("activity:global_task_list"),
        },
        {
            "id": "meetings",
            "title": _("Meetings"),
            "url": reverse_lazy("activity:global_meeting_list"),
        },
        {
            "id": "calls",
            "title": _("Calls"),
            "url": reverse_lazy("activity:global_call_list"),
        },
        {
            "id": "events",
            "title": _("Events"),
            "url": reverse_lazy("activity:global_event_list"),
        },
    ]


@method_decorator(
    permission_required_or_denied(
        ["activity.view_activity", "activity.view_own_activity"]
    ),
    name="dispatch",
)
class ActivityView(LoginRequiredMixin, HorillaView):
    """
    Render the activity page.
    """

    nav_url = reverse_lazy("activity:activity_nav_view")
    list_url = reverse_lazy("activity:activity_tabbed_view")
    kanban_url = reverse_lazy("activity:activity_kanban_tabbed_view")


@method_decorator(htmx_required, name="dispatch")
@method_decorator(
    permission_required(["activity.view_activity", "activity.view_own_activity"]),
    name="dispatch",
)
class ActivityNavbar(LoginRequiredMixin, HorillaNavView):
    """
    Navigation view for managing activity.
    """

    search_url = reverse_lazy("activity:activity_list_view")
    main_url = reverse_lazy("activity:activity_view")
    filterset_class = ActivityFilter
    kanban_url = reverse_lazy("activity:activity_kanban_tabbed_view")
    model_name = "Activity"
    model_app_label = "activity"
    enable_actions = True
    exclude_kanban_fields = "call_type,reminder,activity_type,meeting_host"

    @cached_property
    def new_button(self):
        """
        URL for creating a new Activity..
        """
        if self.request.user.has_perm(
            "activity.add_activity"
        ) or self.request.user.has_perm("activity.add_own_activity"):
            return {
                "url": f"""{reverse_lazy("activity:activity_create_form")}?new=true""",
            }
        return None


@method_decorator(
    permission_required_or_denied(
        ["activity.view_activity", "activity.view_own_activity"]
    ),
    name="dispatch",
)
class AcivityKanbanView(LoginRequiredMixin, HorillaKanbanView):
    """
    Activity Kanban view (all types — kept for backward compatibility).
    """

    model = Activity
    view_id = "activity-kanban"
    filterset_class = ActivityFilter
    search_url = reverse_lazy("activity:activity_list_view")
    main_url = reverse_lazy("activity:activity_view")
    group_by_field = "status"

    actions = AllActivityListView.actions

    columns = [
        (_("Subject"), "subject"),
        (_("Activity Type"), "activity_type"),
        (_("Related To"), "related_object"),
    ]

    @cached_property
    def kanban_attrs(self):
        """
        Defines column attributes for rendering clickable Activity entries
        that load detailed views dynamically using HTMX.
        """

        query_params = {}
        if "section" in self.request.GET:
            query_params["section"] = self.request.GET.get("section")
        query_string = urlencode(query_params)
        attrs = {
            "hx-get": f"{{get_detail_url}}?{query_string}",
            "hx-target": "#mainContent",
            "hx-swap": "outerHTML",
            "hx-push-url": "true",
            "hx-select": "#mainContent",
            "permission": "activity.change_activity",
            "own_permission": "activity.change_own_activity",
            "owner_field": ["owner"],
        }
        return attrs

    def update_kanban_item(self, request):
        """
        After drag-drop, save the status change then reload the active tab's
        kanban via reloadButton. We cannot re-render inline because the registry
        maps Activity → this view (all types), but the tabs each show only one type.
        """
        from horilla.apps import apps as horilla_apps
        from horilla.db.models import ForeignKey

        item_id = request.POST.get("item_id")
        new_column = request.POST.get("new_column")
        app_label = request.POST.get("app_label", "activity")
        model_name = request.POST.get("model_name", "activity")

        try:
            model = horilla_apps.get_model(
                app_label=app_label.split(".")[-1], model_name=model_name
            )
            item = model.all_objects.get(pk=item_id)

            if not self.can_user_modify_item(item):
                messages.error(
                    request, _("You do not have permission to modify this item.")
                )
                return HttpResponse("<script>$('#reloadButton').click();</script>")

            group_by = self.get_group_by_field()
            field = model._meta.get_field(group_by)

            if hasattr(field, "choices") and field.choices:
                valid_choices = dict(field.choices)
                reverse_choices = {v: k for k, v in valid_choices.items()}
                if new_column in reverse_choices:
                    setattr(item, group_by, reverse_choices[new_column])
                elif new_column in valid_choices:
                    setattr(item, group_by, new_column)
            elif isinstance(field, ForeignKey):
                if new_column.lower() == "none":
                    setattr(item, group_by, None)
                else:
                    related_obj = field.related_model.objects.filter(
                        pk=new_column
                    ).first()
                    if related_obj:
                        setattr(item, group_by, related_obj)

            item.save(update_fields=[group_by])

        except Exception as e:
            messages.error(request, str(e))

        return HttpResponse("<script>$('#reloadButton').click();</script>")


_KANBAN_TYPE_COLUMNS = {
    "task": [
        (_("Subject"), "subject"),
        (_("Related To"), "related_object"),
        (_("Priority"), "task_priority"),
        (_("Due Date"), "due_datetime"),
        (_("Assigned To"), "assigned_to"),
    ],
    "meeting": [
        (_("Subject"), "subject"),
        (_("Related To"), "related_object"),
        (_("Start Date"), "get_start_date"),
        (_("End Date"), "get_end_date"),
        (_("Meeting Link"), "get_meeting_url_display"),
    ],
    "log_call": [
        (_("Subject"), "subject"),
        (_("Related To"), "related_object"),
        (_("Purpose"), "call_purpose"),
        (_("Type"), "call_type"),
        (_("Duration"), "call_duration_display"),
    ],
    "event": [
        (_("Subject"), "subject"),
        (_("Related To"), "related_object"),
        (_("Start Date"), "get_start_date"),
        (_("End Date"), "get_end_date"),
        (_("Location"), "location"),
    ],
}


def _make_type_kanban_view(activity_type, view_id):
    """Factory that creates a per-type kanban view class at import time."""

    @method_decorator(htmx_required, name="dispatch")
    @method_decorator(
        permission_required_or_denied(
            ["activity.view_activity", "activity.view_own_activity"]
        ),
        name="dispatch",
    )
    class _TypeKanbanView(LoginRequiredMixin, HorillaKanbanView):
        model = None  # Set after class creation to avoid __init_subclass__ registry collision
        filterset_class = ActivityFilter
        group_by_field = "status"
        height_kanban = "h-[calc(100vh_-_300px)]"
        list_column_visibility = False
        exclude_kanban_fields = "call_type,reminder,activity_type,meeting_host"
        actions = AllActivityListView.actions
        columns = _KANBAN_TYPE_COLUMNS[activity_type]

        @cached_property
        def kanban_attrs(self):
            """Return HTMX attrs for kanban card click navigation with section param."""
            query_params = {}
            if "section" in self.request.GET:
                query_params["section"] = self.request.GET.get("section")
            query_string = urlencode(query_params)
            return {
                "hx-get": f"{{get_detail_url}}?{query_string}",
                "hx-target": "#mainContent",
                "hx-swap": "outerHTML",
                "hx-push-url": "true",
                "hx-select": "#mainContent",
                "permission": "activity.change_activity",
                "own_permission": "activity.change_own_activity",
                "owner_field": ["owner"],
            }

        def get_queryset(self):
            """Filter the queryset to only this kanban view's activity type."""
            return super().get_queryset().filter(activity_type=activity_type)

        @property
        def search_url(self):
            """Return the URL used for search/filter requests."""
            return reverse_lazy("activity:activity_tabbed_view")

        @property
        def main_url(self):
            """Return the main activity list URL."""
            return reverse_lazy("activity:activity_view")

    _TypeKanbanView.__name__ = view_id
    _TypeKanbanView.__qualname__ = view_id
    _TypeKanbanView.view_id = view_id
    _TypeKanbanView.model = (
        Activity  # Assign after class creation — skips __init_subclass__ registry
    )
    return _TypeKanbanView


GlobalTaskKanbanView = _make_type_kanban_view("task", "GlobalTaskKanbanView")
GlobalMeetingKanbanView = _make_type_kanban_view("meeting", "GlobalMeetingKanbanView")
GlobalCallKanbanView = _make_type_kanban_view("log_call", "GlobalCallKanbanView")
GlobalEventKanbanView = _make_type_kanban_view("event", "GlobalEventKanbanView")


@method_decorator(htmx_required, name="dispatch")
@method_decorator(
    permission_required_or_denied(
        ["activity.view_activity", "activity.view_own_activity"]
    ),
    name="dispatch",
)
class AllActivityKanbanTabbedView(LoginRequiredMixin, HorillaTabView):
    """
    Tabbed kanban view — one kanban per activity type, wrapped in the white card shell.
    """

    template_name = "activity_type_tab_view.html"
    view_id = "activity-kanban-type-tabs"
    tab_class = "h-[calc(_100vh_-_260px_)] overflow-hidden"

    tabs = [
        {
            "id": "kanban-tasks",
            "title": _("Tasks"),
            "url": reverse_lazy("activity:global_task_kanban"),
        },
        {
            "id": "kanban-meetings",
            "title": _("Meetings"),
            "url": reverse_lazy("activity:global_meeting_kanban"),
        },
        {
            "id": "kanban-calls",
            "title": _("Calls"),
            "url": reverse_lazy("activity:global_call_kanban"),
        },
        {
            "id": "kanban-events",
            "title": _("Events"),
            "url": reverse_lazy("activity:global_event_kanban"),
        },
    ]


@method_decorator(
    permission_required_or_denied(
        ["activity.view_activity", "activity.view_own_activity"]
    ),
    name="dispatch",
)
class ActivityDetailView(RecentlyViewedMixin, LoginRequiredMixin, HorillaDetailView):
    """
    Detail view for Activity
    """

    model = Activity
    pipeline_field = "status"
    tab_url = reverse_lazy("activity:activity_detail_view_tabs")

    breadcrumbs = [
        (_("Schedule"), "activity:activity_view"),
        (_("Activities"), "activity:activity_view"),
    ]

    excluded_fields = [
        "id",
        "created_at",
        "updated_at",
        "additional_info",
        "history",
        "is_active",
    ]

    actions = AllActivityListView.actions

    @classmethod
    def get_available_fields_for_selector(cls, request, model):
        """
        Method to get the available fields
        """
        pk = request.GET.get("pk")
        if not pk:
            return None
        try:
            activity = model.objects.get(pk=pk)
        except model.DoesNotExist:
            return None

        activity_type = activity.activity_type
        default_header = get_activity_detail_view_fields(activity_type)
        default_details = get_activity_detail_tab_fields(activity_type)

        type_specific = [
            field if isinstance(field, str) else field[0]
            for field in ACTIVITY_TYPE_SPECIFIC_FIELDS.get(activity_type, [])
        ]

        allowed_fields = set(COMMON_FIELDS + type_specific)
        return default_header, default_details, allowed_fields

    def get_body(self):
        """Arrange detail fields based on the activity type."""
        self.body = get_activity_detail_view_fields(self.get_object().activity_type)
        return super().get_body()


@method_decorator(
    permission_required_or_denied(
        ["activity.view_activity", "activity.view_own_activity"]
    ),
    name="dispatch",
)
class ActivityDetailTab(LoginRequiredMixin, HorillaDetailSectionView):
    """
    Activity Detail Tab View
    """

    model = Activity

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        obj = self.get_object()
        self.include_fields = get_activity_detail_tab_fields(obj.activity_type)

        context["body"] = self.body or self.get_default_body()
        return context


@method_decorator(
    permission_required_or_denied(
        ["activity.view_activity", "activity.view_own_activity"]
    ),
    name="dispatch",
)
class ActivityDetailViewTabView(LoginRequiredMixin, HorillaDetailTabView):
    """
    Activity Detail Tab View
    """

    def _prepare_detail_tabs(self):
        self.object_id = self.request.GET.get("object_id")
        self.model = Activity
        self.urls = {
            "details": "activity:activity_details_tab",
            "notes_attachments": "activity:activity_notes_attachments",
            "history": "activity:activity_history_tab_view",
        }
        super()._prepare_detail_tabs()


@method_decorator(
    permission_required_or_denied(
        ["activity.view_activity", "activity.view_own_activity"]
    ),
    name="dispatch",
)
class ActivitynNotesAndAttachments(
    LoginRequiredMixin, HorillaNotesAttachementSectionView
):
    """Notes and Attachments Tab View"""

    model = Activity


@method_decorator(
    permission_required_or_denied(
        ["activity.view_activity", "activity.view_own_activity"]
    ),
    name="dispatch",
)
class ActivityHistoryTabView(LoginRequiredMixin, HorillaHistorySectionView):
    """
    History Tab View
    """

    model = Activity


@method_decorator(htmx_required, name="dispatch")
@method_decorator(
    permission_required_or_denied("activity.delete_activity", modal=True),
    name="dispatch",
)
class ActivityDeleteView(HorillaSingleDeleteView):
    """
    Activity delete view
    """

    model = Activity

    def get_post_delete_response(self):
        activity_type = self.object.activity_type
        if "calendar" in self.request.META.get("HTTP_REFERER", ""):
            return HttpResponse(
                "<script>$('#reloadMainContent').click();$('#reloadButton').click();</script>"
            )

        TAB_MAP = {
            "task": "tab-tasks",
            "meeting": "tab-meetings",
            "log_call": "tab-calls",
            "event": "tab-events",
        }
        if activity_type in TAB_MAP:
            tab_id = TAB_MAP[activity_type]
            return HttpResponse(
                f"<script>"
                f"(function(){{"
                f"var $globalTab = $('#{tab_id}');"
                f"if ($globalTab.length) {{ htmx.trigger($globalTab[0],'click'); return; }}"
                f"localStorage.setItem('horilla_active_activity_tab','{tab_id}');"
                f"$('#reloadButton').click();"
                f"}})();"
                f"</script>"
            )

        return HttpResponse("<script>$('#reloadButton').click();</script>")


@method_decorator(htmx_required, name="dispatch")
class MeetingAddEmailView(LoginRequiredMixin, View):
    """Add an email pill to the external participants field."""

    def post(self, request, *args, **kwargs):
        """Append an external participant email to the hidden comma list and re-render pills."""
        from horilla.shortcuts import render as horilla_render

        email = request.POST.get("email", "").strip()
        field_type = request.POST.get("field_type", "external_participants")
        current_list = request.POST.get(f"{field_type}_email_list", "")
        email_list = (
            [e.strip() for e in current_list.split(",") if e.strip()]
            if current_list
            else []
        )
        if email and email not in email_list:
            email_list.append(email)
        return horilla_render(
            request,
            "email_pills_field.html",
            {
                "email_list": email_list,
                "email_string": ", ".join(email_list),
                "field_type": field_type,
                "current_search": "",
            },
        )


@method_decorator(htmx_required, name="dispatch")
class MeetingRemoveEmailView(LoginRequiredMixin, View):
    """Remove an email pill from the external participants field."""

    def post(self, request, *args, **kwargs):
        """Remove one email from the external participants list and re-render pills."""
        from horilla.shortcuts import render as horilla_render

        email_to_remove = request.POST.get("email_to_remove", "").strip()
        field_type = request.POST.get("field_type", "external_participants")
        current_list = request.POST.get(f"{field_type}_email_list", "")
        email_list = (
            [e.strip() for e in current_list.split(",") if e.strip()]
            if current_list
            else []
        )
        if email_to_remove in email_list:
            email_list.remove(email_to_remove)
        return horilla_render(
            request,
            "email_pills_field.html",
            {
                "email_list": email_list,
                "email_string": ", ".join(email_list),
                "field_type": field_type,
                "current_search": "",
            },
        )
