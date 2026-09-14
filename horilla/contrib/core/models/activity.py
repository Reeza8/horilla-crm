"""
Model to track recently viewed items by users."""

# Third-party imports (Django)
from django.conf import settings

from horilla.db import models
from horilla.menu.sub_section_menu import sub_section_menu
from horilla.registry.permission_registry import permission_exempt_model

# First party imports (Horilla)
from horilla.utils import timezone
from horilla.utils.translation import gettext_lazy as _

# Local imports
from .base import HorillaContentType


class RecentlyViewedManager(models.Manager):
    """
    Manager for RecentlyViewed model to handle recently viewed items.
    """

    def add_viewed_item(self, user, obj):
        """Add or update a recently viewed item for a user."""
        content_type = HorillaContentType.objects.get_for_model(obj)
        self.filter(user=user, content_type=content_type, object_id=obj.pk).delete()
        self.create(user=user, content_type=content_type, object_id=obj.pk)
        if self.filter(user=user).count() > 25:
            recent_ids = (
                self.filter(user=user)
                .order_by("-viewed_at")
                .values_list("id", flat=True)[:20]
            )
            self.filter(user=user).exclude(id__in=recent_ids).delete()

    def get_recently_viewed(self, user, model_class=None, limit=20):
        """Get recently viewed items for a user, optionally filtered by model class.

        Rows can point at different models via a GenericForeignKey, so
        `content_object` can't be select_related/prefetched directly; fetching
        it one row at a time would run one query per row. Instead, group rows
        by content type and batch-fetch each group's objects in one query.
        """
        queryset = self.filter(user=user).order_by("-viewed_at")
        if model_class:
            content_type = HorillaContentType.objects.get_for_model(model_class)
            queryset = queryset.filter(content_type=content_type)
        # Rows can reference since-deleted objects; add_viewed_item caps a
        # user's history at ~25 rows, so scanning the full history (instead
        # of just the first `limit` rows) to backfill those gaps is still
        # bounded and matches the previous behavior.
        rows = list(queryset)
        if not rows:
            return []

        ids_by_content_type = {}
        for row in rows:
            ids_by_content_type.setdefault(row.content_type_id, set()).add(
                row.object_id
            )

        objects_by_content_type = {}
        for content_type_id, object_ids in ids_by_content_type.items():
            content_type = HorillaContentType.objects.get_for_id(content_type_id)
            model = content_type.model_class()
            if model is None:
                continue
            objects_by_content_type[content_type_id] = {
                str(obj.pk): obj for obj in model.objects.filter(pk__in=object_ids)
            }

        results = []
        for row in rows:
            if len(results) >= limit:
                break
            obj = objects_by_content_type.get(row.content_type_id, {}).get(
                str(row.object_id)
            )
            if obj:
                results.append(obj)
        return results


@permission_exempt_model
class RecentlyViewed(models.Model):
    """
    Model to track recently viewed items by users.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="recently_viewed_items",
    )
    content_type = models.ForeignKey(HorillaContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = models.GenericForeignKey("content_type", "object_id")
    viewed_at = models.DateTimeField(default=timezone.now)
    all_objects = models.Manager()
    objects = RecentlyViewedManager()

    class Meta:
        """
        Meta options for the RecentlyViewed model.
        """

        indexes = [
            models.Index(fields=["user", "content_type", "object_id"]),
            models.Index(fields=["user", "viewed_at"]),
        ]
        ordering = ["-viewed_at"]

    def __str__(self):
        return f"{self.user} viewed {self.content_object} at {self.viewed_at}"

    def get_app_section_mapping(self):
        """
        Build a mapping of app_label -> section from registered sub_section_menu items.
        """

        app_to_section = {}
        for cls in sub_section_menu:
            obj = cls()
            app_label = getattr(obj, "app_label", None)
            section = getattr(obj, "section", None)
            if app_label and section:
                app_to_section[app_label] = section
        return app_to_section

    def get_detail_url(self):
        """
        Tries to call any method on the related object that starts with 'get_detail_'.
        Appends section query parameter based on the app_label.
        Falls back to '#' if not found.
        """
        if not self.content_object:
            return "#"

        base_url = None
        for attr in dir(self.content_object):
            if attr.startswith("get_detail_"):
                method = getattr(self.content_object, attr)
                if callable(method):
                    try:
                        base_url = method()
                        break
                    except Exception:
                        continue

        if not base_url or base_url == "#":
            return "#"

        app_label = self.content_type.app_label

        app_to_section = self.get_app_section_mapping()
        section = app_to_section.get(app_label)

        if section:
            separator = "&" if "?" in base_url else "?"
            return f"{base_url}{separator}section={section}"

        return base_url
