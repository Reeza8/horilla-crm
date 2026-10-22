"""
This module defines the organizational models for the Horilla platform
"""

# Standard library imports
import logging

# Django imports
# Third-party imports (Django)
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError

# First party imports (Horilla)
from horilla.db import models
from horilla.urls import reverse_lazy
from horilla.utils.translation import gettext_lazy as _

# Local imports
from .base import HorillaCoreModel

logger = logging.getLogger(__name__)


class Department(HorillaCoreModel):
    """
    Department model
    """

    department_name = models.CharField(
        max_length=50, blank=False, verbose_name=_("Department Name")
    )
    description = models.TextField(blank=True, null=True, verbose_name=_("Description"))

    class Meta:
        """
        Meta options for the Department model.
        """

        verbose_name = _("Department")
        verbose_name_plural = _("Departments")
        unique_together = (("department_name", "company"),)

    def __str__(self):
        return str(self.department_name)

    def get_edit_url(self):
        """
        This method to get edit url
        """
        return reverse_lazy("core:department_update_form", kwargs={"pk": self.pk})

    def get_delete_url(self):
        """
        This method to get delete url
        """

        return reverse_lazy("core:department_delete_view", kwargs={"pk": self.pk})


class Role(HorillaCoreModel):
    """
    Role model
    """

    role_name = models.CharField(max_length=255, verbose_name=_("Role"))
    parent_role = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="subroles",
        verbose_name=_("Parent Role"),
    )
    description = models.TextField(blank=True, null=True, verbose_name=_("Description"))
    permissions = models.ManyToManyField(
        Permission, blank=True, related_name="roles", verbose_name=_("Permissions")
    )

    class Meta:
        """
        Meta options for the Role model.
        """

        verbose_name = _("Role")
        verbose_name_plural = _("Roles")

    def __str__(self):
        return str(self.role_name)

    def get_descendant_ids(self):
        """Return the ids of all subroles (children, grandchildren, ...)."""
        children = {}
        for role_id, parent_id in Role.all_objects.values_list("id", "parent_role_id"):
            children.setdefault(parent_id, []).append(role_id)
        found, stack = set(), list(children.get(self.pk, []))
        while stack:
            role_id = stack.pop()
            if role_id not in found:
                found.add(role_id)
                stack.extend(children.get(role_id, []))
        return found

    def get_select2_excluded_pks(self, field_name):
        """Roles that can't be picked as parent: itself and its subroles."""
        if field_name == "parent_role" and self.pk:
            return {self.pk} | self.get_descendant_ids()
        return set()

    def clean(self):
        """
        Prevent circular hierarchies: a role cannot be its own parent or be
        placed under one of its own subroles.
        """
        super().clean()
        if not self.pk or not self.parent_role_id:
            return
        if self.parent_role_id == self.pk:
            raise ValidationError(
                {"parent_role": _("A role cannot be its own parent.")}
            )
        ancestor_id = self.parent_role_id
        seen = set()
        while ancestor_id and ancestor_id not in seen:
            if ancestor_id == self.pk:
                raise ValidationError(
                    {
                        "parent_role": _(
                            "This role is already a subrole of the selected parent "
                            "chain. Choose a role that is not below this role."
                        )
                    }
                )
            seen.add(ancestor_id)
            ancestor_id = (
                Role.objects.filter(pk=ancestor_id)
                .values_list("parent_role_id", flat=True)
                .first()
            )

    def get_delete_url(self):
        """
        This method to get delete url
        """
        return reverse_lazy("core:delete_role", kwargs={"pk": self.pk})

    def get_edit_url(self):
        """
        This method to get edit url
        """
        return reverse_lazy("core:edit_roles_view", kwargs={"pk": self.pk})


class TeamRole(HorillaCoreModel):
    """
    Team Role model
    """

    team_role_name = models.CharField(
        max_length=50, blank=False, verbose_name=_("Team Role Name")
    )
    description = models.TextField(blank=True, null=True, verbose_name=_("Description"))

    class Meta:
        """
        Meta options for the Team Role model.
        """

        verbose_name = _("Team Role")
        verbose_name_plural = _("Team Roles")

    def __str__(self):
        return str(self.team_role_name)

    def get_edit_url(self):
        """
        This method to get edit url
        """
        return reverse_lazy("core:team_role_update_form", kwargs={"pk": self.pk})

    def get_delete_url(self):
        """
        This method to get delete url
        """

        return reverse_lazy("core:team_role_delete_view", kwargs={"pk": self.pk})


class CustomerRole(HorillaCoreModel):
    """
    Customer Role model
    """

    customer_role_name = models.CharField(
        max_length=50, blank=False, verbose_name=_("Customer Role Name")
    )
    description = models.TextField(blank=True, null=True, verbose_name=_("Description"))

    class Meta:
        """
        Meta options for the Customer Role model.
        """

        verbose_name = _("Customer Role")
        verbose_name_plural = _("Customer Roles")

    def __str__(self):
        return str(self.customer_role_name)

    def get_edit_url(self):
        """
        This method to get edit url
        """
        return reverse_lazy("core:customer_role_update_form", kwargs={"pk": self.pk})

    def get_delete_url(self):
        """
        This method to get delete url
        """

        return reverse_lazy("core:customer_role_delete_view", kwargs={"pk": self.pk})


class PartnerRole(HorillaCoreModel):
    """
    Partner Role model
    """

    partner_role_name = models.CharField(
        max_length=50, blank=False, verbose_name=_("Partner Role Name")
    )
    description = models.TextField(blank=True, null=True, verbose_name=_("Description"))

    class Meta:
        """
        Meta options for the Partner Role model.
        """

        verbose_name = _("Partner Role")
        verbose_name_plural = _("Partner Roles")

    def __str__(self):
        return str(self.partner_role_name)

    def get_edit_url(self):
        """
        This method to get edit url
        """
        return reverse_lazy("core:partner_role_update_form", kwargs={"pk": self.pk})

    def get_delete_url(self):
        """
        This method to get delete url
        """

        return reverse_lazy("core:partner_role_delete_view", kwargs={"pk": self.pk})
