from django.urls import path, include
from rest_framework.routers import DefaultRouter

from safety.viewsets import (
    ConversationViewSet,
    SafetyLogViewSet,
    DocumentViewSet,
    AnalyticsViewSet,
)

router = DefaultRouter()
router.register(r'conversations', ConversationViewSet, basename='conversation')
router.register(r'safety-logs', SafetyLogViewSet, basename='safetylog')
router.register(r'documents', DocumentViewSet, basename='document')
router.register(r'analytics', AnalyticsViewSet, basename='analytics')

urlpatterns = [
    path('', include(router.urls)),
]
