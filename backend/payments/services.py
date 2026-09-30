"""Checkout helpers shared by the REST views and the gateway webhooks."""

import base64

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction

from .models import Payment


def provider_configured(provider):
    if provider == Payment.Provider.PAYME:
        return bool(settings.PAYME_KEY and settings.PAYME_MERCHANT_ID)
    if provider == Payment.Provider.CLICK:
        return bool(settings.CLICK_SECRET_KEY and settings.CLICK_SERVICE_ID)
    return False


def create_checkout(user, plan, provider):
    """Return a pending payment row for this user/plan/provider.

    Reuses the most recent pending row so repeated clicks on the pay button
    do not pile up identical checkouts. The user row is locked so two
    concurrent checkouts cannot both create a pending payment.
    """
    with transaction.atomic():
        User = get_user_model()
        User.objects.select_for_update().get(pk=user.pk)
        payment = (
            Payment.objects.filter(
                user=user, plan=plan, provider=provider, status=Payment.Status.PENDING
            )
            .order_by("-created_at")
            .first()
        )
        if payment is None:
            payment = Payment.objects.create(
                user=user,
                plan=plan,
                provider=provider,
                amount_uzs=plan.price_uzs,
            )
        return payment


def payme_checkout_url(payment, return_url=None, lang="uz"):
    """Payme receipt URL: <checkout>/base64(m=...;ac.payment=...;a=...;c=...)."""
    parts = [
        f"m={settings.PAYME_MERCHANT_ID}",
        f"ac.payment={payment.id}",
        f"a={payment.amount_uzs * 100}",  # tiyin
        f"l={lang if lang in ('ru', 'uz', 'en') else 'ru'}",
    ]
    if return_url:
        parts.append(f"c={return_url}")
    payload = ";".join(parts)
    token = base64.b64encode(payload.encode("utf-8")).decode("ascii")
    return f"{settings.PAYME_CHECKOUT_URL.rstrip('/')}/{token}"


def click_checkout_url(payment):
    """Click payment link (my.click.uz web form)."""
    params = (
        f"service_id={settings.CLICK_SERVICE_ID}"
        f"&merchant_id={settings.CLICK_MERCHANT_ID}"
        f"&amount={payment.amount_uzs}"
        f"&transaction_param={payment.id}"
    )
    return f"{settings.CLICK_PAY_URL}?{params}"


def payment_url(payment, return_url=None, lang="uz"):
    if payment.provider == Payment.Provider.PAYME:
        return payme_checkout_url(payment, return_url=return_url, lang=lang)
    return click_checkout_url(payment)
