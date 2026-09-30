"""Click Shop API webhook (Prepare / Complete).

Click `POST /webhooks/click/` sends an x-www-form-urlencoded body with
`action=0` (Prepare) or `action=1` (Complete) plus an md5 `sign_string`:

  Prepare: md5(click_trans_id + service_id + secret + merchant_trans_id
               + amount + action + sign_time)
  Complete: md5(click_trans_id + service_id + secret + merchant_trans_id
                + merchant_prepare_id + amount + action + sign_time)

Error codes follow Click's Shop API catalogue:
  -1 signature, -2 amount, -3 parameters/action, -4 state (already done),
  -5 invoice, -6 transaction (merchant_prepare_id), -9 cancelled.
"""

import hashlib
import hmac
import logging

from django.conf import settings
from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from premium.services import activate_plan

from .models import Payment

logger = logging.getLogger(__name__)

ERR_SIGN = -1
ERR_AMOUNT = -2
ERR_PARAMS = -3
ERR_STATE = -4
ERR_INVOICE = -5
ERR_TRANSACTION = -6
ERR_CANCELLED = -9

CLICK_PROVIDER = Payment.Provider.CLICK


def _md5(value: str) -> str:
    return hashlib.md5(value.encode("utf-8")).hexdigest()


def _compute_sign(data, merchant_prepare_id: str) -> str:
    secret = settings.CLICK_SECRET_KEY
    if data["action"] == "0":
        raw = (
            f"{data['click_trans_id']}{data['service_id']}{secret}"
            f"{data['merchant_trans_id']}{data['amount']}{data['action']}"
            f"{data['sign_time']}"
        )
    else:
        raw = (
            f"{data['click_trans_id']}{data['service_id']}{secret}"
            f"{data['merchant_trans_id']}{merchant_prepare_id}{data['amount']}"
            f"{data['action']}{data['sign_time']}"
        )
    return _md5(raw)


def _err(click_trans_id, merchant_trans_id, code, note):
    body = {"error": code, "error_note": note}
    if click_trans_id:
        body["click_trans_id"] = click_trans_id
    if merchant_trans_id:
        body["merchant_trans_id"] = merchant_trans_id
    return JsonResponse(body)


def _ok(click_trans_id, merchant_trans_id, extra=None):
    body = {
        "click_trans_id": click_trans_id,
        "merchant_trans_id": merchant_trans_id,
        "error": 0,
        "error_note": "Success",
    }
    if extra:
        body.update(extra)
    return JsonResponse(body)


def _amount_matches(payment, raw) -> bool:
    try:
        got = float(raw)
    except (ValueError, TypeError):
        return False
    return abs(got - float(payment.amount_uzs)) <= 0.01


def _get_click_payment(pk_raw, merchant_trans_id):
    try:
        pk = int(pk_raw)
    except (ValueError, TypeError):
        return None
    if str(pk) != str(merchant_trans_id):
        return None
    return Payment.objects.select_related("plan", "user").filter(
        pk=pk, provider=CLICK_PROVIDER
    ).first()


def _handle_prepare(data, click_trans_id, merchant_trans_id):
    payment = _get_click_payment(merchant_trans_id, merchant_trans_id)
    if payment is None:
        return _err(click_trans_id, merchant_trans_id, ERR_INVOICE, "Invoice not found")
    if not _amount_matches(payment, data["amount"]):
        return _err(click_trans_id, merchant_trans_id, ERR_AMOUNT, "Wrong amount")
    if payment.status == Payment.Status.PAID:
        return _err(click_trans_id, merchant_trans_id, ERR_STATE, "Already paid")
    if payment.status != Payment.Status.PENDING:
        return _err(click_trans_id, merchant_trans_id, ERR_INVOICE, "Invoice not payable")

    payment.meta = {
        **payment.meta,
        "click_trans_id": click_trans_id,
        "click_paydoc_id": data.get("click_paydoc_id", ""),
    }
    payment.save(update_fields=["meta", "updated_at"])
    return _ok(
        click_trans_id,
        merchant_trans_id,
        {"merchant_prepare_id": str(payment.pk)},
    )


def _handle_complete(data, click_trans_id, merchant_trans_id, incoming_error):
    payment = _get_click_payment(data.get("merchant_prepare_id"), merchant_trans_id)
    if payment is None:
        return _err(
            click_trans_id, merchant_trans_id, ERR_TRANSACTION, "Transaction not found"
        )
    if not _amount_matches(payment, data["amount"]):
        return _err(click_trans_id, merchant_trans_id, ERR_AMOUNT, "Wrong amount")

    if incoming_error != 0:
        # Click reports the payment failed / was cancelled by the user.
        with transaction.atomic():
            payment = Payment.objects.select_for_update().get(pk=payment.pk)
            if payment.status == Payment.Status.PAID:
                return _err(
                    click_trans_id,
                    merchant_trans_id,
                    ERR_STATE,
                    "Payment already completed",
                )
            if payment.status != Payment.Status.CANCELLED:
                payment.status = Payment.Status.CANCELLED
                payment.meta = {**payment.meta, "click_error": incoming_error}
                payment.save(update_fields=["status", "meta", "updated_at"])
        return _err(
            click_trans_id, merchant_trans_id, ERR_CANCELLED, "Payment cancelled"
        )

    with transaction.atomic():
        payment = Payment.objects.select_for_update().get(pk=payment.pk)
        if payment.status == Payment.Status.PAID:
            return _err(
                click_trans_id, merchant_trans_id, ERR_STATE, "Already confirmed"
            )
        if payment.status == Payment.Status.CANCELLED:
            return _err(
                click_trans_id, merchant_trans_id, ERR_CANCELLED, "Payment cancelled"
            )
        subscription = activate_plan(payment.user, payment.plan)
        payment.status = Payment.Status.PAID
        payment.paid_at = timezone.now()
        payment.subscription = subscription
        payment.meta = {**payment.meta, "click_trans_id": click_trans_id}
        payment.save(
            update_fields=["status", "paid_at", "subscription", "meta", "updated_at"]
        )
    return _ok(
        click_trans_id,
        merchant_trans_id,
        {"merchant_confirm_id": str(payment.pk)},
    )


@csrf_exempt
@require_POST
def click_webhook(request):
    if not settings.CLICK_SECRET_KEY or not settings.CLICK_SERVICE_ID:
        logger.error("Click webhook: CLICK_SECRET_KEY/CLICK_SERVICE_ID sozlanmagan")
        return _err("", "", -91, "Payment gateway disabled")

    post = request.POST
    data = {
        "click_trans_id": str(post.get("click_trans_id", "") or "").strip(),
        "service_id": str(post.get("service_id", "") or "").strip(),
        "merchant_trans_id": str(post.get("merchant_trans_id", "") or "").strip(),
        "merchant_prepare_id": str(post.get("merchant_prepare_id", "") or "").strip(),
        "click_paydoc_id": str(post.get("click_paydoc_id", "") or "").strip(),
        "amount": str(post.get("amount", "") or "").strip(),
        "action": str(post.get("action", "") or "").strip(),
        "sign_time": str(post.get("sign_time", "") or "").strip(),
        "sign_string": str(post.get("sign_string", "") or "").strip(),
    }
    try:
        incoming_error = int(post.get("error", 0) or 0)
    except (ValueError, TypeError):
        incoming_error = 0

    if data["action"] not in ("0", "1"):
        return _err(
            data["click_trans_id"], data["merchant_trans_id"], ERR_PARAMS, "Invalid action"
        )

    expected_sign = _compute_sign(data, data["merchant_prepare_id"])
    if not hmac.compare_digest(expected_sign, data["sign_string"]):
        logger.warning("Click webhook: sign tekshiruvi mag'lubiyati")
        return _err(
            data["click_trans_id"], data["merchant_trans_id"], ERR_SIGN, "CHECK SIGNATURE"
        )

    if data["service_id"] != str(settings.CLICK_SERVICE_ID):
        return _err(
            data["click_trans_id"],
            data["merchant_trans_id"],
            ERR_PARAMS,
            "Wrong service_id",
        )

    try:
        if data["action"] == "0":
            return _handle_prepare(
                data, data["click_trans_id"], data["merchant_trans_id"]
            )
        return _handle_complete(
            data, data["click_trans_id"], data["merchant_trans_id"], incoming_error
        )
    except Exception:  # noqa: BLE001 - gateway must always get a JSON answer
        logger.exception("Click webhook: ishlov berishda xato")
        return _err(
            data["click_trans_id"], data["merchant_trans_id"], -92, "System error"
        )
