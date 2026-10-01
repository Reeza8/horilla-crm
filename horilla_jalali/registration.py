"""Inject Jalali date/time picker assets and History formatting without patching core."""

from horilla.registry.asset_registry import register_html
from horilla.registry.history_registry import register_history_datetime_formatter
from horilla_jalali.history import format_history_datetime_as_jalali

register_html(
    "horilla_jalali/inject_html/jalali_assets_head.html",
    slot="head_end",
    priority=95,
)

register_html(
    "horilla_jalali/inject_html/jalali_assets_js.html",
    slot="body_end",
    priority=80,
)

register_history_datetime_formatter(format_history_datetime_as_jalali)
