# Define your notifications forms here
"""
Forms for Horilla Notification module.

This module contains Django forms for managing email templates,
mail configurations, and mail-related functionality.
"""

# Third-party imports (Django)
from django import forms

from horilla.contrib.utils.methods import sanitize_html

# First-party (Horilla)
from horilla.core.exceptions import ValidationError
from horilla.utils.translation import gettext_lazy as _

# Local imports
from .models import NotificationTemplate


class NotificationTemplateForm(forms.ModelForm):
    """Form for creating and editing Horilla notification Templates"""

    field_order = [
        "title",
        "content_type",
        "message",
        "company",
    ]

    class Meta:
        """Meta class for NotificationTemplateForm."""

        model = NotificationTemplate
        fields = "__all__"
        exclude = [
            "is_active",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
            "additional_info",
        ]

    def clean_title(self):
        """
        Clean and validate the title field.

        Returns:
            str: The cleaned and stripped title.

        Raises:
            ValidationError: If the title is empty or contains only whitespace.
        """
        title = self.cleaned_data.get("title")
        if not title or title.strip() == "":
            raise ValidationError(_("Template title is required."))
        return title.strip()

    def clean_message(self):
        """
        Clean and validate the message field.

        Returns:
            str: The cleaned message content.

        Raises:
            ValidationError: If the message is empty or contains XSS patterns.
        """
        message = self.cleaned_data.get("message")
        if not message or message.strip() == "":
            raise ValidationError(_("Template message is required."))
        return sanitize_html(message)
