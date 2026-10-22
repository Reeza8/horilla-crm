"""
Feature and asset registration for the mobile app.
"""

# First party imports (Horilla)
from horilla.registry.asset_registry import register_html
from horilla.registry.feature import register_feature

from .registry import FEATURE_NAME, REGISTRY_KEY
from .utils import MOBILE_PAGE

# Only models that pass ``features=["mobile"]`` themselves, never every model
# registered with ``all=True``.
register_feature(FEATURE_NAME, REGISTRY_KEY, auto_register_all=False)

# Same RTL font and stylesheet the desktop layout and login page get.
register_html(
    "inject_html/rtl_assets.html",
    slot="head_end",
    priority=90,
    page=MOBILE_PAGE,
)
