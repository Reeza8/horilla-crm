"""
Bottom navigation of the mobile layout.
"""

# First party imports (Horilla)
from horilla.urls import reverse
from horilla.utils.translation import gettext_lazy as _

# One entry per mobile page, in display order.
NAV_ITEMS = [
    {
        "url_name": "today",
        "label": _("My work"),
        "icon": "fa-regular fa-calendar-check",
    },
    {
        "url_name": "agenda",
        "label": _("Agenda"),
        "icon": "fa-regular fa-calendar-days",
        # Adding from the Agenda belongs to this tab.
        "also_active_on": ("agenda_activity",),
    },
    {
        "url_name": "records",
        "label": _("Records"),
        "icon": "fa-solid fa-magnifying-glass",
        # The record page belongs to this tab.
        "also_active_on": (
            "record",
            "log_activity",
            "add_note",
            "activity_detail",
            "note_detail",
            "edit_activity",
            "edit_note",
        ),
    },
]


def get_nav_items(request):
    """Return the bottom navigation entries, marking the current page active."""
    match = getattr(request, "resolver_match", None)
    current = match.url_name if match and match.namespace == "mobile" else None
    return [
        {
            "url": reverse(f"mobile:{item['url_name']}"),
            "label": item["label"],
            "icon": item["icon"],
            "active": current == item["url_name"]
            or current in item.get("also_active_on", ()),
        }
        for item in NAV_ITEMS
    ]


def agenda_url(day=None):
    """The Agenda, on ``day`` when given."""
    url = reverse("mobile:agenda")
    return f"{url}?date={day.isoformat()}" if day else url
