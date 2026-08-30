"""
Filter classes for Horilla core models.

Defines filtersets for user, company, department, roles, and holiday models
with search fields and field exclusions for use in list views and APIs.
"""

# First party imports (Horilla)
from horilla.auth.models import User
from horilla.contrib.generics.filters import HorillaFilterSet

# Local imports
from .models import (
    Company,
    CustomerRole,
    Department,
    FieldRequirement,
    Holiday,
    PartnerRole,
    Role,
    TeamRole,
)


class UserFilter(HorillaFilterSet):
    """Filterset for User model with search on first name, last name, and email."""

    class Meta:
        """Meta options for UserFilter."""

        model = User
        fields = "__all__"
        exclude = [
            "profile",
            "password",
            "last_login",
            "date_joined",
            "username",
            "is_staff",
        ]
        search_fields = ["first_name", "email", "last_name"]


class CompanyFilter(HorillaFilterSet):
    """Filterset for Company model with search on company name."""

    class Meta:
        """Meta options for CompanyFilter."""

        model = Company
        fields = "__all__"
        exclude = ["icon"]
        search_fields = ["name"]


class DepartmentFilter(HorillaFilterSet):
    """Filterset for Department model with search on department name."""

    class Meta:
        """Meta options for DepartmentFilter."""

        model = Department
        fields = "__all__"
        exclude = ["additional_info"]
        search_fields = ["department_name"]


class FieldRequirementFilter(HorillaFilterSet):
    """Filterset for FieldRequirement with search on the configured field."""

    class Meta:
        """Meta options for FieldRequirementFilter."""

        model = FieldRequirement
        fields = "__all__"
        exclude = ["additional_info"]
        search_fields = ["field_name"]


class TeamRoleFilter(HorillaFilterSet):
    """Filterset for TeamRole model with search on team role name."""

    class Meta:
        """Meta options for TeamRoleFilter."""

        model = TeamRole
        fields = "__all__"
        exclude = ["additional_info"]
        search_fields = ["team_role_name"]


class RoleFilter(HorillaFilterSet):
    """Filterset for TeamRole model with search on team role name."""

    class Meta:
        """Meta options for TeamRoleFilter."""

        model = Role
        fields = "__all__"
        exclude = ["additional_info"]
        search_fields = ["role_name"]


class CustomerRoleFilter(HorillaFilterSet):
    """Filterset for CustomerRole model with search on customer role name."""

    class Meta:
        """Meta options for CustomerRoleFilter."""

        model = CustomerRole
        fields = "__all__"
        exclude = ["additional_info"]
        search_fields = ["customer_role_name"]


class PartnerRoleFilter(HorillaFilterSet):
    """Filterset for PartnerRole model with search on partner role name."""

    class Meta:
        """Meta options for PartnerRoleFilter."""

        model = PartnerRole
        fields = "__all__"
        exclude = ["additional_info"]
        search_fields = ["partner_role_name"]


class HolidayFilter(HorillaFilterSet):
    """Filterset for Holiday model with search on holiday name."""

    class Meta:
        """Meta options for HolidayFilter."""

        model = Holiday
        fields = "__all__"
        exclude = ["additional_info"]
        search_fields = ["name"]
