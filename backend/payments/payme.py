"""Payme Merchant API webhook (JSON-RPC 2.0).

Payme `POST /webhooks/payme/` with:
    Authorization: Basic base64(PAYME_LOGIN:PAYME_KEY)
    Content-Type: text/json
    {"method": "...", "params": {...}, "id": 1}

Protocol reference: https://developer.help.paycom.uz/protokol-merchant-api/
Every response is HTTP 200 (per the protocol); only bad credentials -> 401.
"""

import base64
import hmac
import json
import logging
import time

from django.conf import settings
from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from premium.services import activate_plan

from .models import Payment

logger = logging.getLogger(__name__)

# Payme Merchant API error codes.
ERR_AMOUNT = -31001
ERR_TRANSACTION_NOT_FOUND = -31003
ERR_CANNOT_PERFORM = -31008
ERR_ACCOUNT = -31050  # -31050..-31099: bad account field (data names it)

PAYME_PROVIDER = Payment.Provider.PAYME


class PaymeError(Exception):
    def __init__(self, code, message, data=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data


def _now_ms():
    return int(time.time() * 1000)


def _auth_ok(request) -> bool:
    key = getattr(settings, "PAYME_KEY", "") or ""
    if not key:
        return False  # fail closed: no key -> webhook unusable
    header = request.headers.get("Authorization", "") or ""
    expected_logins = {
        login for login in (getattr(settings, "PAYME_LOGIN", ""), "Paycom") if login
    }
    for login in expected_logins:
        expected = "Basic " + base64.b64encode(f"{login}:{key}".encode()).decode()
        if hmac.compare_digest(header, expected):
            return True
    return False


def _payment_from_account(account) -> Payment:
    raw = ""
    if isinstance(account, dict):
        raw = str(account.get("payment", "") or "").strip()
    try:
        payment = Payment.objects.select_related("plan", "user").get(
            pk=int(raw), provider=PAYME_PROVIDER
        )
    except (ValueError, TypeError, Payment.DoesNotExist):
        raise PaymeError(
            ERR_ACCOUNT,
            "To'lov topilmadi",
            data={"payment": raw},
        )
    return payment


def _payment_by_txn(txn) -> Payment:
    try:
        return Payment.objects.select_related("plan", "user").get(
            provider=PAYME_PROVIDER, gateway_ref=str(txn)
        )
    except (Payment.DoesNotExist, ValueError, TypeError):
        raise PaymeError(ERR_TRANSACTION_NOT_FOUND, "Tranzaksiya topilmadi")


def _check_amount(payment, amount):
    expected = payment.amount_uzs * 100  # tiyin
    try:
        got = int(amount)
    except (ValueError, TypeError):
        got = None
    if got != expected:
        raise PaymeError(ERR_AMOUNT, "To'lov summasi noto'g'ri", data={"amount": expected})


def _state(payment) -> int:
    stored = payment.meta.get("state")
    if stored is not None:
        return int(stored)
    if payment.status == Payment.Status.PAID:
        return 2
    if payment.status == Payment.Status.CANCELLED:
        return -1
    return 1


def _require_pending(payment):
    if payment.status == Payment.Status.PENDING:
        return
    raise PaymeError(ERR_CANNOT_PERFORM, "To'lovni bajarib bo'lmaydi")


# ---- RPC methods ------------------------------------------------------------


def check_perform_transaction(params):
    payment = _payment_from_account(params.get("account"))
    _require_pending(payment)
    _check_amount(payment, params.get("amount"))
    return {"allow": True}


def create_transaction(params):
    txn = str(params.get("id", "") or "").strip()
    if not txn:
        raise PaymeError(-32602, "params.id kutilmoqda")

    existing = Payment.objects.filter(provider=PAYME_PROVIDER, gateway_ref=txn).first()
    if existing is not None:
        # Retried CreateTransaction: answer idempotently.
        return {
            "create_time": int(existing.meta.get("create_time") or 0),
            "transaction": str(existing.pk),
            "state": _state(existing),
        }

    payment = _payment_from_account(params.get("account"))
    _require_pending(payment)
    _check_amount(payment, params.get("amount"))

    create_time = int(params.get("time") or _now_ms())
    payment.gateway_ref = txn
    payment.meta = {
        **payment.meta,
        "create_time": create_time,
        "state": 1,
    }
    payment.save(update_fields=["gateway_ref", "meta", "updated_at"])
    return {"create_time": create_time, "transaction": str(payment.pk), "state": 1}


def perform_transaction(params):
    txn = str(params.get("id", "") or "").strip()
    payment = _payment_by_txn(txn)

    with transaction.atomic():
        payment = Payment.objects.select_for_update().get(pk=payment.pk)
        if payment.status == Payment.Status.PAID:
            return {
                "transaction": str(payment.pk),
                "perform_time": int(payment.meta.get("perform_time") or 0),
                "state": 2,
            }
        if payment.status != Payment.Status.PENDING:
            raise PaymeError(ERR_CANNOT_PERFORM, "To'lovni bajarib bo'lmaydi")

        perform_time = int(params.get("time") or _now_ms())
        subscription = activate_plan(payment.user, payment.plan)
        payment.status = Payment.Status.PAID
        payment.paid_at = timezone.now()
        payment.subscription = subscription
        payment.meta = {**payment.meta, "perform_time": perform_time, "state": 2}
        payment.save(
            update_fields=["status", "paid_at", "subscription", "meta", "updated_at"]
        )
    return {"transaction": str(payment.pk), "perform_time": perform_time, "state": 2}


def cancel_transaction(params):
    txn = str(params.get("id", "") or "").strip()
    payment = _payment_by_txn(txn)

    with transaction.atomic():
        payment = Payment.objects.select_for_update().get(pk=payment.pk)
        state = _state(payment)
        if state in (-1, -2):
            return {
                "transaction": str(payment.pk),
                "cancel_time": int(payment.meta.get("cancel_time") or 0),
                "state": state,
            }

        cancel_time = int(params.get("time") or _now_ms())
        if payment.status == Payment.Status.PAID:
            new_state = -2  # cancelled after perform -> refund
            if payment.subscription_id:
                subscription = payment.subscription
                subscription.ends_at = timezone.now()
                subscription.save(update_fields=["ends_at"])
        else:
            new_state = -1  # cancelled before perform

        payment.status = Payment.Status.CANCELLED
        payment.meta = {
            **payment.meta,
            "cancel_time": cancel_time,
            "state": new_state,
            "cancel_reason": str(params.get("reason", "") or ""),
        }
        payment.save(update_fields=["status", "meta", "updated_at"])
    return {"transaction": str(payment.pk), "cancel_time": cancel_time, "state": new_state}


def check_transaction(params):
    payment = _payment_by_txn(params.get("id"))
    return {
        "transaction": str(payment.pk),
        "create_time": int(payment.meta.get("create_time") or 0),
        "perform_time": int(payment.meta.get("perform_time") or 0),
        "cancel_time": int(payment.meta.get("cancel_time") or 0),
        "state": _state(payment),
    }


METHODS = {
    "CheckPerformTransaction": check_perform_transaction,
    "CreateTransaction": create_transaction,
    "PerformTransaction": perform_transaction,
    "CancelTransaction": cancel_transaction,
    "CheckTransaction": check_transaction,
}


def _rpc_body(payload, result=None, error=None):
    body = {}
    if error is not None:
        body["error"] = error
    else:
        body["result"] = result
    if isinstance(payload, dict) and "id" in payload:
        body["id"] = payload["id"]
    return body


@csrf_exempt
@require_POST
def payme_webhook(request):
    if not _auth_ok(request):
        logger.warning("Payme webhook: ruxsatsiz so'rov")
        return JsonResponse({"error": "unauthorized"}, status=401)

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return JsonResponse(
            _rpc_body(None, error={"code": -32700, "message": "Parse error"})
        )

    method = payload.get("method") if isinstance(payload, dict) else None
    params = payload.get("params") if isinstance(payload, dict) else None
    if not isinstance(params, dict):
        params = {}
    handler = METHODS.get(method)
    if handler is None:
        return JsonResponse(
            _rpc_body(payload, error={"code": -32601, "message": "Method not found"})
        )

    try:
        result = handler(params)
    except PaymeError as exc:
        error = {"code": exc.code, "message": exc.message}
        if exc.data is not None:
            error["data"] = exc.data
        return JsonResponse(_rpc_body(payload, error=error))
    except Exception:  # noqa: BLE001 - gateway must always get a JSON answer
        logger.exception("Payme webhook: %s ishlov berishda xato", method)
        return JsonResponse(
            _rpc_body(payload, error={"code": -32603, "message": "Internal error"})
        )
    return JsonResponse(_rpc_body(payload, result=result))
