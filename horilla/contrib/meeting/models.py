"""Models for the Horilla Meeting Integration app."""

# Third-party imports (Django)
from django.conf import settings

from horilla.contrib.core.models import HorillaCoreModel, Role

# First party imports (Horilla)
from horilla.db import models
from horilla.utils.translation import gettext_lazy as _

PROVIDER_ZOOM = "zoom"
PROVIDER_GOOGLE_MEET = "google_meet"
PROVIDER_MS_TEAMS = "ms_teams"

MEETING_PROVIDER_CHOICES = [
    (PROVIDER_ZOOM, _("Zoom")),
    (PROVIDER_GOOGLE_MEET, _("Google Meet")),
    (PROVIDER_MS_TEAMS, _("Microsoft Teams")),
]

ACCESS_ALL = "all"
ACCESS_ROLES = "roles"
ACCESS_USERS = "users"

ACCESS_CHOICES = [
    (ACCESS_ALL, _("All Users")),
    (ACCESS_ROLES, _("Specific Roles")),
    (ACCESS_USERS, _("Specific Users")),
]


class MeetingIntegrationSetting(HorillaCoreModel):
    """
    Company-level single toggle for the meeting integration.
    One row per company — controls whether any meeting provider is available
    and who can use it.
    """

    is_enabled = models.BooleanField(
        default=False,
        verbose_name=_("Enabled"),
    )
    access_type = models.CharField(
        max_length=10,
        choices=ACCESS_CHOICES,
        default=ACCESS_ALL,
        verbose_name=_("Access Type"),
        help_text=_("Who can generate meeting links."),
    )
    allowed_roles = models.ManyToManyField(
        Role,
        blank=True,
        verbose_name=_("Allowed Roles"),
        related_name="meeting_integrations",
    )
    allowed_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        verbose_name=_("Allowed Users"),
        related_name="meeting_integrations",
    )

    class Meta:
        """Meta for MeetingIntegrationSetting."""

        verbose_name = _("Meeting Integration Setting")
        verbose_name_plural = _("Meeting Integration Settings")

    def __str__(self):
        return f"Meeting Integration – {'on' if self.is_enabled else 'off'}"

    def user_has_access(self, user):
        """Return True if *user* is allowed to use the meeting integration."""
        if not self.is_enabled:
            return False
        if self.access_type == ACCESS_ALL:
            return True
        if self.access_type == ACCESS_ROLES:
            user_role_id = getattr(user, "role_id", None)
            if not user_role_id:
                return False
            return self.allowed_roles.filter(pk=user_role_id).exists()
        if self.access_type == ACCESS_USERS:
            return self.allowed_users.filter(pk=user.pk).exists()
        return False

    @classmethod
    def _get_cached_setting(cls, request, company):
        """
        Resolve the setting row for ``company``, caching the result on
        ``request`` so repeated menu-condition checks within the same
        request (settings menu + my-settings menu) reuse one query
        instead of each issuing their own.
        """
        if not company:
            return None
        if request is None:
            return cls.all_objects.filter(company=company).first()

        cache_attr = "_meeting_integration_setting_cache"
        cached = getattr(request, cache_attr, None)
        if cached is None:
            cached = {}
            setattr(request, cache_attr, cached)
        if company.pk not in cached:
            cached[company.pk] = cls.all_objects.filter(company=company).first()
        return cached[company.pk]

    @classmethod
    def meeting_enabled(cls, request=None):
        """Used as a menu condition — returns True when the integration is on for this company."""
        from horilla.contrib.utils.middlewares import _thread_local

        if request is None:
            request = getattr(_thread_local, "request", None)
        if request is None:
            return False
        company = getattr(request.user, "company", None)
        if not company:
            return False
        setting = cls._get_cached_setting(request, company)
        return bool(setting and setting.is_enabled)

    @classmethod
    def user_has_menu_access(cls, request=None):
        """Menu condition — True only when integration is enabled AND current user has access."""
        from horilla.contrib.utils.middlewares import _thread_local

        if request is None:
            request = getattr(_thread_local, "request", None)
        if request is None:
            return False
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return False
        company = getattr(user, "company", None)
        if not company:
            return False
        return cls.user_can_access(user, company, request=request)

    @classmethod
    def get_for_company(cls, company):
        """Return integration settings for ``company``, creating the row if missing."""
        if not company:
            return None
        setting, _ = cls.all_objects.get_or_create(company=company)
        return setting

    @classmethod
    def user_can_access(cls, user, company, request=None):
        """Return True if meeting integration is enabled and ``user`` is allowed for ``company``."""
        setting = cls._get_cached_setting(request, company)
        return bool(setting and setting.user_has_access(user))


class UserMeetingConfig(HorillaCoreModel):
    """
    Per-user personal meeting room / link for a given provider.
    The user stores their static meeting URL here (e.g. Zoom personal room).
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="meeting_configs",
        verbose_name=_("User"),
    )
    provider = models.CharField(
        max_length=30,
        choices=MEETING_PROVIDER_CHOICES,
        verbose_name=_("Provider"),
    )
    personal_meeting_url = models.URLField(
        max_length=1000,
        blank=True,
        verbose_name=_("Personal Meeting URL"),
        help_text=_("Your static personal meeting room link, if available."),
    )

    class Meta:
        """Meta for UserMeetingConfig."""

        unique_together = ("user", "provider", "company")
        verbose_name = _("User Meeting Config")
        verbose_name_plural = _("User Meeting Configs")

    def __str__(self):
        return f"{self.user} – {self.get_provider_display()}"


class ZoomOAuthConfig(HorillaCoreModel):
    """Per-user Zoom OAuth credentials and token."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="zoom_oauth_config",
        verbose_name=_("User"),
    )
    client_id = models.CharField(
        max_length=255, blank=True, verbose_name=_("Client ID")
    )
    client_secret = models.CharField(
        max_length=255, blank=True, verbose_name=_("Client Secret")
    )
    token = models.JSONField(default=dict, blank=True, verbose_name=_("OAuth Token"))
    oauth_state = models.CharField(
        max_length=255, blank=True, null=True, verbose_name=_("OAuth State")
    )
    connected_email = models.EmailField(
        blank=True, verbose_name=_("Connected Account Email")
    )

    class Meta:
        """Django metadata for per-user Zoom OAuth settings."""

        verbose_name = _("Zoom OAuth Config")
        verbose_name_plural = _("Zoom OAuth Configs")

    def has_credentials(self):
        """True when client ID and secret are both set."""
        return bool(self.client_id and self.client_secret)

    def is_connected(self):
        """True when OAuth token response includes an access_token."""
        return bool(self.token and self.token.get("access_token"))

    def __str__(self):
        return f"Zoom – {self.user}"


class MicrosoftTeamsOAuthConfig(HorillaCoreModel):
    """Per-user Microsoft Teams OAuth credentials and token."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="teams_oauth_config",
        verbose_name=_("User"),
    )
    client_id = models.CharField(
        max_length=255, blank=True, verbose_name=_("Client ID (Application ID)")
    )
    client_secret = models.CharField(
        max_length=255, blank=True, verbose_name=_("Client Secret")
    )
    tenant_id = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_("Tenant ID"),
        help_text=_("Your Azure AD tenant ID, or 'common' for multi-tenant apps."),
    )
    token = models.JSONField(default=dict, blank=True, verbose_name=_("OAuth Token"))
    oauth_state = models.CharField(
        max_length=255, blank=True, null=True, verbose_name=_("OAuth State")
    )
    connected_email = models.EmailField(
        blank=True, verbose_name=_("Connected Account Email")
    )

    class Meta:
        """Django metadata for per-user Teams OAuth settings."""

        verbose_name = _("Microsoft Teams OAuth Config")
        verbose_name_plural = _("Microsoft Teams OAuth Configs")

    def has_credentials(self):
        """True when client credentials and tenant ID are set."""
        return bool(self.client_id and self.client_secret and self.tenant_id)

    def is_connected(self):
        """True when OAuth token response includes an access_token."""
        return bool(self.token and self.token.get("access_token"))

    def __str__(self):
        return f"Teams – {self.user}"
