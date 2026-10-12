"""
URLs for the field settings pages (custom fields, field requirements and
form layouts), all under the single ``field_management`` namespace.
"""

# First party imports (Horilla)
from horilla.urls import include, path

# Local imports
from . import views

app_name = "field_management"

custom_field_patterns = [
    path("", views.CustomFieldView.as_view(), name="custom_fields_view"),
    path("navbar/", views.CustomFieldNavbar.as_view(), name="custom_fields_navbar"),
    path("list/", views.CustomFieldListView.as_view(), name="custom_fields_list"),
    path("create/", views.CustomFieldFormView.as_view(), name="custom_fields_create"),
    path(
        "edit/<int:pk>/",
        views.CustomFieldFormView.as_view(),
        name="custom_fields_edit",
    ),
    path(
        "delete/<int:pk>/",
        views.CustomFieldDeleteView.as_view(),
        name="custom_fields_delete",
    ),
]

field_requirement_patterns = [
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

form_layout_patterns = [
    path(
        "",
        views.FormLayoutListPageView.as_view(),
        name="form_layout_view",
    ),
    path("nav/", views.FormLayoutNavbar.as_view(), name="form_layout_navbar"),
    path("list/", views.FormLayoutListView.as_view(), name="form_layout_list"),
    path(
        "create/",
        views.FormLayoutCreateView.as_view(),
        name="form_layout_create",
    ),
    path(
        "<int:ct>/",
        views.FormLayoutView.as_view(),
        name="form_layout_detail",
    ),
    path(
        "<int:ct>/nav/",
        views.FormLayoutDetailNavbar.as_view(),
        name="form_layout_detail_nav",
    ),
    path(
        "<int:ct>/edit/",
        views.FormLayoutEditorView.as_view(forced_mode="edit"),
        name="form_layout_edit",
    ),
    path(
        "editor/",
        views.FormLayoutEditorView.as_view(),
        name="form_layout_editor",
    ),
    path(
        "save/",
        views.FormLayoutSaveView.as_view(),
        name="form_layout_save",
    ),
    path(
        "reset/",
        views.FormLayoutResetView.as_view(),
        name="form_layout_reset",
    ),
]

urlpatterns = [
    path("custom-fields/", include(custom_field_patterns)),
    path("field-requirements/", include(field_requirement_patterns)),
    path("form-layouts/", include(form_layout_patterns)),
]
