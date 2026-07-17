"""Package metadata for the `horilla.contrib.reports` app."""

# First party imports (Horilla)
from horilla.utils.translation import gettext_lazy as _

__version__ = "1.11.4"
__module_name__ = "Reports"
__release_date__ = ""
__description__ = _(
    "Module for creating and customizing reports across all system modules."
)
__icon__ = "assets/icons/icon5.svg"

__1_11_4__ = _(
    "Avoid RelatedObjectDoesNotExist in create-report form_invalid when related objects "
    "are missing."
)

__1_11_3__ = _(
    "Re-raise HttpNotFound with exception chaining in report detail, export, and CRUD "
    "views to preserve context."
)

__1_11_2__ = _(
    "Added pivot cell active state and filter badge with clear action. Fixed detail table "
    "filtering for empty and null pivot group values."
)

__1_11_1__ = _(
    "Removed redundant fields attributes superseded by form_class on report CRUD views, "
    "standardized first-party import groups, and added docstrings for pylint compliance."
)

__1_10_1__ = _(
    "Report forms aligned with HorillaModelForm layout: field_order and "
    'Meta.fields = "__all__" with Meta.exclude; folder and column HTMX unchanged.'
)

__1_10_0__ = _(
    "Release 1.10: reports ship under contrib with app label reports. "
    "Cross-app report wiring, ContentType references, namespaces, and registrations "
    "updated for the contrib naming scheme."
)

__1_2_1__ = _(
    "Improved report compatibility with dashboard multi-widget support, "
    "enhanced chart_value_field handling, and minor stability improvements "
    "for report rendering and filter processing."
)

__1_2_0__ = _(
    "Added support for advanced chart types including Treemap, Area charts, "
    "Heatmaps, Sankey diagrams, and Radar charts. Improved compatibility with "
    "the new visualization and analytics framework."
)

__1_1_0__ = _(
    "Migrated from Django AppConfig to Horilla AppLauncher and and replaced"
    "Django utilities with horilla.utils.decorators, horilla.utils.translation,"
    "and horilla.shortcuts where applicable."
)
