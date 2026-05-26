"""
Admin registration for the calls app
"""

# Register your calls models here.
from django.contrib import admin

from .models import AgentMapping, CallIntegrationSetting, CallLog, CallProvider

admin.site.register(CallProvider)
admin.site.register(AgentMapping)
admin.site.register(CallLog)
admin.site.register(CallIntegrationSetting)
