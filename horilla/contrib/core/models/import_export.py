"""
This module defines the models for import and export functionalities in the Horilla platform.
"""

# Standard library imports
import logging

# Django imports
# Third-party imports (Django)
from django.conf import settings
from django.utils.html import format_html

from horilla.apps import apps
from horilla.contrib.utils.methods import render_template

# First party imports (Horilla)
from horilla.db import models
from horilla.urls import reverse_lazy
from horilla.utils.choices import DAY_CHOICES
from horilla.utils.translation import gettext_lazy as _

# Local imports
from .base import HorillaCoreModel

logger = logging.getLogger(__name__)


class HorillaImport(models.Model):
    """
    Horilla Import model for permission management
    """

    class Meta:
        """
        Meta options for the HorillaImport model.
        """

        managed = False
        default_permissions = ()
        permissions = (("can_view_horilla_import", _("Can View Global Import")),)
        verbose_name = _("Global Import")


class ImportHistory(HorillaCoreModel):
    """
    Model to track the history of data imports.
    """

    STATUS_CHOICES = [
        ("processing", _("Processing")),
        ("success", _("Success")),
        ("partial", _("Partial Success")),
        ("failed", _("Failed")),
    ]

    import_name = models.CharField(max_length=255, verbose_name=_("Import Name"))
    module_name = models.CharField(max_length=100, verbose_name=_("Module Name"))
    app_label = models.CharField(max_length=100, verbose_name=_("App Label"))
    original_filename = models.CharField(max_length=255, verbose_name=_("Filename"))
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="processing",
        verbose_name=_("Status"),
    )
    total_rows = models.IntegerField(default=0, verbose_name=_("Total Counts"))
    created_count = models.IntegerField(default=0)
    updated_count = models.IntegerField(default=0)
    error_count = models.IntegerField(default=0)
    success_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=0, verbose_name=_("Success Rate (%)")
    )
    imported_file_path = models.CharField(
        max_length=500, blank=True, null=True, verbose_name=_("Imported File")
    )
    error_file_path = models.CharField(
        max_length=500, blank=True, null=True, verbose_name=_("Error File")
    )
    import_option = models.CharField(
        max_length=10, help_text=_("1=create, 2=update, 3=both")
    )
    match_fields = models.JSONField(default=list, blank=True)
    field_mappings = models.JSONField(default=dict, blank=True)
    error_summary = models.JSONField(default=list, blank=True)
    duration_seconds = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        null=True,
        blank=True,
        verbose_name=_("Duration (seconds)"),
    )

    class Meta:
        """
        Meta options for the ImportHistory model.
        """

        ordering = ["-created_at"]
        verbose_name = _("Import History")
        verbose_name_plural = _("Import Histories")

    def __str__(self):
        return f"{self.import_name} - {self.module_name} ({self.status})"

    @property
    def successful_rows(self):
        """Returns the count of successful rows."""
        return self.created_count + self.updated_count

    def error_list(self):
        """Returns the HTML for the is_default column in the list view."""
        html = render_template(
            path="import/error_list_col.html",
            context={"instance": self},
        )
        return html

    def imported_file(self):
        """Returns the HTML for the is_default column in the list view."""
        html = render_template(
            path="import/import_file_col.html",
            context={"instance": self},
        )
        return html

    @property
    def has_errors(self):
        """Returns True if there are any errors."""
        return self.error_count > 0

    @property
    def is_complete(self):
        """Returns True if the import process is complete."""
        return self.status in ["success", "partial", "failed"]

    @property
    def status_color_class(self):
        """Returns the CSS class for the status badge."""
        colors = {
            "processing": "bg-blue-100 text-blue-800",
            "success": "bg-green-100 text-green-800",
            "partial": "bg-yellow-100 text-yellow-800",
            "failed": "bg-red-100 text-red-800",
        }
        return colors.get(self.status, "bg-gray-100 text-gray-800")

    @property
    def formatted_duration(self):
        """Returns the duration in a human-readable format."""
        if self.duration_seconds is None:
            return "N/A"

        seconds = float(self.duration_seconds)
        if seconds < 60:
            return f"{seconds:.1f}s"
        if seconds < 3600:
            return f"{seconds / 60:.1f}m"

        return f"{seconds / 3600:.1f}h"

    @property
    def module_verbose_name(self):
        """Returns the verbose name of the model based on module_name and app_label."""
        if not self.module_name or not self.app_label:
            return self.module_name or ""

        try:
            model = apps.get_model(self.app_label, self.module_name)
            return model._meta.verbose_name
        except (LookupError, AttributeError):
            # If model not found, return the module_name as fallback
            return self.module_name


class HorillaExport(models.Model):
    """
    Horilla Export model for permission management
    """

    class Meta:
        """
        Meta options for the HorillaExport model.
        """

        managed = False
        default_permissions = ()
        permissions = (("can_view_horilla_export", _("Can View Global Export")),)
        verbose_name = _("Global Export")


class ExportSchedule(HorillaCoreModel):
    """
    Model to store export schedules for users.
    """

    FREQUENCY_CHOICES = (
        ("daily", _("Daily")),
        ("weekly", _("Weekly")),
        ("monthly", _("Monthly")),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="export_schedules",
    )
    modules = models.JSONField(
        help_text=_("List of model names, e.g. ['Employee', 'Department']"),
        verbose_name=_("Modules"),
    )
    fields = models.JSONField(
        default=dict,
        blank=True,
        help_text=_(
            "Dict of {model_name: [field_name, ...]}. Empty/missing entries "
            "export all exportable fields for that model."
        ),
        verbose_name=_("Fields"),
    )
    export_format = models.CharField(
        max_length=5,
        choices=[("csv", _("CSV")), ("xlsx", _("Excel")), ("pdf", _("PDF"))],
        verbose_name=_("Export Format"),
    )
    frequency = models.CharField(
        max_length=10, choices=FREQUENCY_CHOICES, verbose_name=_("Frequency")
    )

    # ---- monthly / weekly specifics ----
    day_of_month = models.PositiveSmallIntegerField(
        null=True, blank=True, help_text=_("1-31 for monthly")
    )
    weekday = models.CharField(
        max_length=9,
        null=True,
        blank=True,
        choices=DAY_CHOICES,
    )

    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)

    # Yearly
    yearly_day_of_month = models.PositiveSmallIntegerField(null=True, blank=True)
    yearly_month = models.PositiveSmallIntegerField(
        null=True, blank=True, choices=[(i, i) for i in range(1, 13)]
    )

    last_run = models.DateField(
        null=True, blank=True, verbose_name=_("Last Executed On")
    )

    class Meta:
        """
        Meta options for the ExportSchedule model.
        """

        verbose_name = _("Export Schedule")
        verbose_name_plural = _("Export Schedules")

    PROPERTY_LABELS = {
        "module_names_display": "Modules",
        "last_executed": "Last Executed On",
        "frequency_display": "Schedule Details",
    }

    def __str__(self):
        return f"{self.user} – {self.frequency} – {self.export_format}"

    def module_names_display(self):
        """Return the module names as a comma-separated string."""
        return ", ".join(self.modules)

    def last_executed(self):
        """Return formatted last run date"""
        if self.last_run:
            return self.last_run
        return _("Not run yet")

    def get_detail_url(self):
        """
        This method to get detail url
        """
        return reverse_lazy("core:schedule_export_detail_view", kwargs={"pk": self.pk})

    def get_edit_url(self):
        """
        This method to get edit url
        """
        return reverse_lazy("core:schedule_modal")

    def get_delete_url(self):
        """
        This method to get delete url
        """

        return reverse_lazy("core:schedule_export_delete", kwargs={"pk": self.pk})

    def frequency_display(self):
        """Return formatted frequency and date."""

        if self.frequency == "daily":
            text = _("Every day")

        elif self.frequency == "weekly":
            weekday = self.get_weekday_display() if self.weekday else ""
            text = _("Every") + " " + weekday.capitalize()

        elif self.frequency == "monthly" and self.day_of_month:
            text = _("Day") + f" {self.day_of_month} " + _("of every month")

        elif self.frequency == "yearly":
            if self.yearly_day_of_month and self.yearly_month:
                text = f"{self.yearly_day_of_month}/{self.yearly_month}"
            else:
                text = _("Yearly")
        else:
            text = ""

        if self.start_date:
            if self.end_date:
                return format_html(
                    "{}<br><span class='text-xs text-gray-500'>From: {} to {}</span>",
                    text,
                    self.start_date.strftime("%d %b %Y"),
                    self.end_date.strftime("%d %b %Y"),
                )
            return format_html(
                "{}<br><span class='text-xs text-gray-500'>From: {}</span>",
                text,
                self.start_date.strftime("%d %b %Y"),
            )
        return format_html("{}", text)
