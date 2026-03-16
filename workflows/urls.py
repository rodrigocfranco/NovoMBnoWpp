"""Workflows URL configuration."""

from django.urls import path

from workflows.views import WhatsAppWebhookView

urlpatterns = [
    path("webhook/whatsapp/", WhatsAppWebhookView.as_view(), name="whatsapp-webhook"),
]
