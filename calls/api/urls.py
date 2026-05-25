"""DRF URL router for the Horilla Calls Integration API."""

from rest_framework.routers import DefaultRouter

from .views import CallProviderViewSet, AgentMappingViewSet, CallLogViewSet

router = DefaultRouter()
router.register("providers", CallProviderViewSet, basename="callprovider")
router.register("agents", AgentMappingViewSet, basename="agentmapping")
router.register("logs", CallLogViewSet, basename="calllog")

urlpatterns = router.urls
