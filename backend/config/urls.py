from django.contrib import admin
from django.urls import include, path

from payments.click import click_webhook
from payments.payme import payme_webhook
from telegrambot.webhook import telegram_webhook

urlpatterns = [
    path("admin/", admin.site.urls),
    path("webhooks/telegram/", telegram_webhook, name="telegram-webhook"),
    path("webhooks/payme/", payme_webhook, name="payme-webhook"),
    path("webhooks/click/", click_webhook, name="click-webhook"),
    path("", include("core.urls")),
]