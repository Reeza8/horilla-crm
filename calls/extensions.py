"""Extends activity app with call-specific behaviour via _inherit_model/_inherit_mixin."""

from horilla.contrib.core.models import HorillaCoreModel
from horilla.extension.mixin import MixinExtension
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


class CallListActionsExtension(MixinExtension):
    """Prepend the "Call Now" action to the call activity tab's action list."""

    _inherit_mixin = "horilla.contrib.activity.views.list_view.tab_views.CallListView"

    def get_context_data(self, original, *args, **kwargs):
        context = original(*args, **kwargs)
        actions = [_CALL_NOW_ACTION, *context.get("visible_actions", [])]
        actions += context.get("dropdown_actions", [])
        if len(actions) > self.max_visible_actions:
            context["visible_actions"] = actions[: self.max_visible_actions]
            context["dropdown_actions"] = actions[self.max_visible_actions :]
            context["use_dropdown"] = True
        else:
            context["visible_actions"] = actions
            context["dropdown_actions"] = []
            context["use_dropdown"] = False
        return context


class ActivityCallExtension(HorillaCoreModel):
    """Injects get_call_now_url onto the Activity model."""

    _inherit_model = "activity.Activity"

    def get_call_now_url(self):
        """Return the click-to-call URL pre-filled with this activity's linked object."""
        model_name = self.content_type.model if self.content_type_id else ""
        object_id = self.object_id or ""
        base = reverse_lazy("calls:click_to_call")
        return f"{base}?model_name={model_name}&object_id={object_id}"
