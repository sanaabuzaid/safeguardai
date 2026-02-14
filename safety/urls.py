from django.urls import path, include
from safety import views

app_name = 'safety'

urlpatterns = [
    path('webhook/whatsapp/', views.whatsapp_webhook, name='whatsapp_webhook'),
    path('webhook/status/', views.webhook_status, name='webhook_status'),
    path('webhook/test/', views.test_message, name='test_message'),
    path('', include('safety.api_urls')),
    path('dashboard/', views.dashboard_view, name='dashboard'),
]
