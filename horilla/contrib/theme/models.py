"""
Models for the theme app
"""

# Create your theme models here.
# Third-party imports (Django)
from django.core.validators import RegexValidator

from horilla.contrib.core.models import HorillaCoreModel

# First party imports (Horilla)
from horilla.db import models, transaction
from horilla.utils.translation import gettext_lazy as _


class HorillaColorTheme(models.Model):
    """
    Model to store predefined color themes for Horilla
    """

    name = models.CharField(max_length=100, unique=True, verbose_name=_("Name"))
    description = models.TextField(blank=True, verbose_name=_("Description"))

    # Primary Colors
    primary_50 = models.CharField(
        max_length=7, validators=[RegexValidator(r"^#[0-9A-Fa-f]{6}$")]
    )
    primary_100 = models.CharField(
        max_length=7, validators=[RegexValidator(r"^#[0-9A-Fa-f]{6}$")]
    )
    primary_200 = models.CharField(
        max_length=7, validators=[RegexValidator(r"^#[0-9A-Fa-f]{6}$")]
    )
    primary_300 = models.CharField(
        max_length=7, validators=[RegexValidator(r"^#[0-9A-Fa-f]{6}$")]
    )
    primary_400 = models.CharField(
        max_length=7, validators=[RegexValidator(r"^#[0-9A-Fa-f]{6}$")]
    )
    primary_500 = models.CharField(
        max_length=7, validators=[RegexValidator(r"^#[0-9A-Fa-f]{6}$")]
    )
    primary_600 = models.CharField(
        max_length=7, validators=[RegexValidator(r"^#[0-9A-Fa-f]{6}$")]
    )
    primary_700 = models.CharField(
        max_length=7, validators=[RegexValidator(r"^#[0-9A-Fa-f]{6}$")]
    )
    primary_800 = models.CharField(
        max_length=7, validators=[RegexValidator(r"^#[0-9A-Fa-f]{6}$")]
    )
    primary_900 = models.CharField(
        max_length=7, validators=[RegexValidator(r"^#[0-9A-Fa-f]{6}$")]
    )

    # Dark Colors
    dark_25 = models.CharField(
        max_length=7, validators=[RegexValidator(r"^#[0-9A-Fa-f]{6}$")]
    )
    dark_50 = models.CharField(
        max_length=7, validators=[RegexValidator(r"^#[0-9A-Fa-f]{6}$")]
    )
    dark_100 = models.CharField(
        max_length=7, validators=[RegexValidator(r"^#[0-9A-Fa-f]{6}$")]
    )
    dark_200 = models.CharField(
        max_length=7, validators=[RegexValidator(r"^#[0-9A-Fa-f]{6}$")]
    )
    dark_300 = models.CharField(
        max_length=7, validators=[RegexValidator(r"^#[0-9A-Fa-f]{6}$")]
    )
    dark_400 = models.CharField(
        max_length=7, validators=[RegexValidator(r"^#[0-9A-Fa-f]{6}$")]
    )
    dark_500 = models.CharField(
        max_length=7, validators=[RegexValidator(r"^#[0-9A-Fa-f]{6}$")]
    )
    dark_600 = models.CharField(
        max_length=7, validators=[RegexValidator(r"^#[0-9A-Fa-f]{6}$")]
    )

    # Secondary Colors
    secondary_50 = models.CharField(
        max_length=7, validators=[RegexValidator(r"^#[0-9A-Fa-f]{6}$")]
    )
    secondary_100 = models.CharField(
        max_length=7, validators=[RegexValidator(r"^#[0-9A-Fa-f]{6}$")]
    )
    secondary_200 = models.CharField(
        max_length=7, validators=[RegexValidator(r"^#[0-9A-Fa-f]{6}$")]
    )
    secondary_300 = models.CharField(
        max_length=7, validators=[RegexValidator(r"^#[0-9A-Fa-f]{6}$")]
    )
    secondary_400 = models.CharField(
        max_length=7, validators=[RegexValidator(r"^#[0-9A-Fa-f]{6}$")]
    )
    secondary_500 = models.CharField(
        max_length=7, validators=[RegexValidator(r"^#[0-9A-Fa-f]{6}$")]
    )
    secondary_600 = models.CharField(
        max_length=7, validators=[RegexValidator(r"^#[0-9A-Fa-f]{6}$")]
    )
    secondary_700 = models.CharField(
        max_length=7, validators=[RegexValidator(r"^#[0-9A-Fa-f]{6}$")]
    )
    secondary_800 = models.CharField(
        max_length=7, validators=[RegexValidator(r"^#[0-9A-Fa-f]{6}$")]
    )
    secondary_900 = models.CharField(
        max_length=7, validators=[RegexValidator(r"^#[0-9A-Fa-f]{6}$")]
    )

    # Surface color (kanban/group-by background; match each theme, not derived)
    surface = models.CharField(
        max_length=9,
        validators=[RegexValidator(r"^#[0-9A-Fa-f]{6}([0-9A-Fa-f]{2})?$")],
        default="#e9edf0ba",
    )

    is_default = models.BooleanField(
        default=False,
        verbose_name=_("Is Default"),
        help_text=_(
            "Set as default theme for login page.\
            Only one theme can be default across all companies."
        ),
    )

    class Meta:
        """
        Meta option for HorillaColorTheme model
        """

        ordering = ["name"]
        verbose_name = _("Color Theme")
        verbose_name_plural = _("Color Themes")

    def __str__(self):
        return f"{self.name}"

    def save(self, *args, **kwargs):
        """
        Override save to ensure only one default theme exists.
        Uses a transaction to ensure atomicity.
        """
        with transaction.atomic():
            if self.is_default:
                query = HorillaColorTheme.objects.filter(is_default=True)
                if self.pk:
                    query = query.exclude(pk=self.pk)
                query.update(is_default=False)
            super().save(*args, **kwargs)
            if self.is_default and self.pk:
                HorillaColorTheme.objects.filter(is_default=True).exclude(
                    pk=self.pk
                ).update(is_default=False)

    @classmethod
    def ensure_single_default(cls):
        """
        Ensure only one default theme exists. Fixes any duplicate defaults.
        Keeps the most recently updated one as default.
        """
        defaults = cls.objects.filter(is_default=True).order_by("-id")
        if defaults.count() > 1:
            keep_default = defaults.first()
            defaults.exclude(pk=keep_default.pk).update(is_default=False)
            return keep_default
        return defaults.first()

    @classmethod
    def get_default_theme(cls):
        """
        Get the default theme for login page
        Returns the theme object or None
        """
        cls.ensure_single_default()

        default_theme = cls.objects.filter(is_default=True).first()
        if default_theme:
            return default_theme
        return cls.objects.filter(name="Coral Red Theme (Default)").first()


class CompanyTheme(HorillaCoreModel):
    """
    Model to store company-wide theme settings
    """

    theme = models.ForeignKey(
        HorillaColorTheme,
        on_delete=models.SET_NULL,
        null=True,
        related_name="organizations",
        verbose_name=_("Theme"),
    )

    class Meta:
        """
        Meta option for CompanyTheme model
        """

        verbose_name = _("Company Theme")
        verbose_name_plural = _("Company Themes")

    def __str__(self):
        return f"{self.theme} - {self.company}"

    @classmethod
    def get_default_theme(cls):
        """
        Get the default theme for login page
        Returns the theme object or None
        """
        return HorillaColorTheme.get_default_theme()

    @classmethod
    def get_theme_for_company(cls, company):
        """
        Get the theme for a specific company
        Returns the theme object or default theme
        """
        if not company:
            return cls.get_default_theme()

        company_theme = (
            cls.all_objects.filter(company=company).select_related("theme").first()
        )
        if company_theme and company_theme.theme:
            return company_theme.theme

        return HorillaColorTheme.objects.filter(
            name="Coral Red Theme (Default)"
        ).first()
