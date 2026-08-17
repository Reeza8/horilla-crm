"""Inject Jalali date/time picker assets without patching core templates."""

from horilla.registry.asset_registry import register_html

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
