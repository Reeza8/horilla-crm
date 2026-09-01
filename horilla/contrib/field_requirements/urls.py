"""
URLs for the field requirements settings page.
"""

# First party imports (Horilla)
from horilla.urls import path

# Local imports
from . import views

app_name = "field_requirements"

urlpatterns = [
    path(
        "",
        views.FieldRequirementView.as_view(),
        name="field_requirement_view",
    ),
    path(
        "nav/",
        views.FieldRequirementNavbar.as_view(),
        name="field_requirement_nav_view",
    ),
    path(
        "list/",
        views.FieldRequirementListView.as_view(),
        name="field_requirement_list_view",
    ),
    path(
        "create/",
        views.FieldRequirementFormView.as_view(),
        name="field_requirement_create_form",
    ),
    path(
        "update/<int:pk>/",
        views.FieldRequirementFormView.as_view(),
        name="field_requirement_update_form",
    ),
    path(
        "delete/<int:pk>/",
        views.FieldRequirementDeleteView.as_view(),
        name="field_requirement_delete_view",
    ),
    path(
        "field-choices/",
        views.FieldRequirementFieldChoicesView.as_view(),
        name="field_requirement_field_choices",
    ),
]
