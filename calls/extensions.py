"""Extends activity app with call-specific behaviour via _inherit and action registry."""

from horilla.contrib.activity.views.list_view.tab_views import _CALL_TAB_ACTIONS
from horilla.contrib.core.models import HorillaCoreModel
from horilla.urls import reverse_lazy

_CALL_NOW_ACTION = {
    "action": "Call Now",
    "icon": "fa-solid fa-phone",
    "attrs": """
                hx-get="{get_call_now_url}"
                hx-target="#modalBox"
                hx-swap="innerHTML"
                onclick="openModal()"
            """,
}
_CALL_TAB_ACTIONS.insert(0, _CALL_NOW_ACTION)


class ActivityCallExtension(HorillaCoreModel):
    """Injects get_call_now_url onto the Activity model."""

    _inherit_model = "activity.Activity"

    def get_call_now_url(self):
        """Return the click-to-call URL pre-filled with this activity's linked object."""
        model_name = self.content_type.model if self.content_type_id else ""
        object_id = self.object_id or ""
        base = reverse_lazy("calls:click_to_call")
        return f"{base}?model_name={model_name}&object_id={object_id}"
