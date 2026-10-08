"""Django admin configuration for mail models."""

# Third-party imports (Django)
from django.contrib import admin

# Local imports
from .models import (
    HorillaMail,
    HorillaMailAttachment,
    HorillaMailConfiguration,
    HorillaMailTemplate,
    IncomingMail,
)

# Register your mail models here.

admin.site.register(HorillaMailConfiguration)
admin.site.register(HorillaMail)
admin.site.register(HorillaMailAttachment)
admin.site.register(HorillaMailTemplate)
admin.site.register(IncomingMail)
