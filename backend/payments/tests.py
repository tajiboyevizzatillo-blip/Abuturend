import base64
import hashlib
import json
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from premium.models import Subscription, SubscriptionPlan
from payments.models import Payment

User = get_user_model()

PAYME_LOGIN = "Paycom"
PAYME_KEY = "test-payme-key"
PAYME_MERCHANT_ID = "587f72c72cac0d162c722ae2"
CLICK_SERVICE_ID = 94048
CLICK_MERCHANT_ID = 1111
CLICK_SECRET_KEY = "click-secret"

GATEWAY_SETTINGS = {
    "PAYME_LOGIN": PAYME_LOGIN,
    "PAYME_KEY": PAYME_KEY,
    "PAYME_MERCHANT_ID": PAYME_MERCHANT_ID,
    "PAYME_CHECKOUT_URL": "https://checkout.paycom.uz",
    "CLICK_SERVICE_ID": CLICK_SERVICE_ID,
    "CLICK_MERCHANT_ID": CLICK_MERCHANT_ID,
    "CLICK_SECRET_KEY": CLICK_SECRET_KEY,
    "CLICK_PAY_URL": "https://my.click.uz/services/pay",
}


def payme_auth():
    token = base64.b64encode(f"{PAYME_LOGIN}:{PAYME_KEY}".encode()).decode()
    return f"Basic {token}"


def click_sign(payload, complete=False, merchant_prepare_id=""):
    raw = (
        f"{payload['click_trans_id']}{payload['service_id']}{CLICK_SECRET_KEY}"
        f"{payload['merchant_trans_id']}"
    )
    if complete:
        raw += merchant_prepare_id
    raw += f"{payload['amount']}{payload['action']}{payload['sign_time']}"
    return hashlib.md5(raw.encode()).hexdigest()


@override_settings(**GATEWAY_SETTINGS)
class CheckoutTests(APITestCase):
    def setUp(self):
        # Throttle history lives in LocMemCache, which the test runner does not
        # reset, and each test's rolled-back transaction reuses the same user
        # pk. Without this the bucket is shared by every test in the process and
        # the "checkout" scope (20/min) starts answering 429 part-way through the
        # suite, in tests that have nothing to do with rate limiting.
        cache.clear()
        self.user = User.objects.create_user(
            username="payer", password="Passw0rd!", role=User.Role.STUDENT
        )
        self.other = User.objects.create_user(
            username="other", password="Passw0rd!", role=User.Role.STUDENT
        )
        self.free = SubscriptionPlan.objects.create(
            code="free-trial",
            tier=SubscriptionPlan.Tier.FREE,
            name_uz="Bepul",
            price_uzs=0,
            max_sessions_per_day=3,
        )
        self.pro = SubscriptionPlan.objects.create(
            code="pro-monthly",
            tier=SubscriptionPlan.Tier.PRO,
            name_uz="PRO",
            price_uzs=49_000,
            max_sessions_per_day=None,
        )
        self.client.force_login(self.user)

    def test_checkout_requires_login(self):
        self.client.logout()
        res = self.client.post(
            "/api/payments/checkout/",
            {"plan_code": "pro-monthly", "provider": "payme"},
            format="json",
        )
        self.assertIn(
            res.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )

    def test_checkout_free_plan_rejected(self):
        res = self.client.post(
            "/api/payments/checkout/",
            {"plan_code": "free-trial", "provider": "payme"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_checkout_unknown_plan_rejected(self):
        res = self.client.post(
            "/api/payments/checkout/",
            {"plan_code": "nope", "provider": "payme"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_checkout_payme_returns_receipt_url(self):
        res = self.client.post(
            "/api/payments/checkout/",
            {"plan_code": "pro-monthly", "provider": "payme"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data["provider"], "payme")
        self.assertEqual(res.data["amount_uzs"], 49_000)
        self.assertEqual(res.data["status"], Payment.Status.PENDING)

        prefix = "https://checkout.paycom.uz/"
        self.assertTrue(res.data["payment_url"].startswith(prefix))
        params = base64.b64decode(res.data["payment_url"][len(prefix):]).decode()
        self.assertIn(f"m={PAYME_MERCHANT_ID}", params)
        self.assertIn(f"ac.payment={res.data['id']}", params)
        self.assertIn(f"a={49_000 * 100}", params)  # tiyin
        self.assertTrue(
            Payment.objects.filter(
                user=self.user, provider=Payment.Provider.PAYME, status="pending"
            ).exists()
        )

    def test_checkout_click_returns_pay_link(self):
        res = self.client.post(
            "/api/payments/checkout/",
            {"plan_code": "pro-monthly", "provider": "click"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        url = res.data["payment_url"]
        self.assertTrue(url.startswith("https://my.click.uz/services/pay?"))
        self.assertIn(f"service_id={CLICK_SERVICE_ID}", url)
        self.assertIn(f"merchant_id={CLICK_MERCHANT_ID}", url)
        self.assertIn("amount=49000", url)
        self.assertIn(f"transaction_param={res.data['id']}", url)

    def test_checkout_return_path_keeps_locale_and_payment_id(self):
        # The frontend sends "/ru/premium/payment/{id}/" so the gateway sends
        # the student back to the localised status page.
        res = self.client.post(
            "/api/payments/checkout/",
            {
                "plan_code": "pro-monthly",
                "provider": "payme",
                "return_path": "/ru/premium/payment/{id}/",
            },
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertIn(
            f"/ru/premium/payment/{res.data['id']}/", res.data["return_url"]
        )
        # Payme embeds the return URL in the receipt (c= param, base64).
        prefix = "https://checkout.paycom.uz/"
        receipt = base64.b64decode(res.data["payment_url"][len(prefix):]).decode()
        self.assertIn("/ru/premium/payment/", receipt)

    def test_checkout_accepts_plain_payment_page_path(self):
        res = self.client.post(
            "/api/payments/checkout/",
            {
                "plan_code": "pro-monthly",
                "provider": "payme",
                "return_path": "/uz/premium/payment/{id}",
            },
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertIn(f"/uz/premium/payment/{res.data['id']}", res.data["return_url"])

    def test_checkout_rejects_backslash_redirect(self):
        """Browsers normalise `\\` to `/`, so `/\\/evil.com` is an open redirect.

        The value is handed to the payment gateway as the post-payment redirect,
        which makes it a phishing vector delivered through a trusted domain.
        """
        for hostile in (
            "/\\/evil.com",
            "/uz\\evil.com",
            "/uz/premium/payment/\\evil.com",
            "//evil.com",
            "https://evil.com",
            "/dashboard",
            "/uz/premium/payment/1\r\nSet-Cookie: x=1",
        ):
            res = self.client.post(
                "/api/payments/checkout/",
                {
                    "plan_code": "pro-monthly",
                    "provider": "payme",
                    "return_path": hostile,
                },
                format="json",
            )
            self.assertEqual(
                res.status_code,
                status.HTTP_400_BAD_REQUEST,
                msg=f"accepted hostile return_path: {hostile!r}",
            )

    def test_checkout_rejects_pending_payment_when_return_path_invalid(self):
        res = self.client.post(
            "/api/payments/checkout/",
            {
                "plan_code": "pro-monthly",
                "provider": "payme",
                "return_path": "/\\/evil.com",
            },
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        # A rejected request must not leave a payment row behind.
        self.assertFalse(Payment.objects.filter(user=self.user).exists())

    def test_checkout_reuses_pending_payment(self):
        first = self.client.post(
            "/api/payments/checkout/",
            {"plan_code": "pro-monthly", "provider": "click"},
            format="json",
        )
        second = self.client.post(
            "/api/payments/checkout/",
            {"plan_code": "pro-monthly", "provider": "click"},
            format="json",
        )
        self.assertEqual(first.data["id"], second.data["id"])
        self.assertEqual(
            Payment.objects.filter(user=self.user, provider="click").count(), 1
        )

    def test_status_visible_to_owner_only(self):
        res = self.client.post(
            "/api/payments/checkout/",
            {"plan_code": "pro-monthly", "provider": "click"},
            format="json",
        )
        payment_id = res.data["id"]
        own = self.client.get(f"/api/payments/{payment_id}/")
        self.assertEqual(own.status_code, status.HTTP_200_OK)
        self.assertEqual(own.data["status"], Payment.Status.PENDING)
        self.assertIn("payment_url", own.data)

        self.client.force_login(self.other)
        foreign = self.client.get(f"/api/payments/{payment_id}/")
        self.assertEqual(foreign.status_code, status.HTTP_404_NOT_FOUND)

    def test_status_endpoint_preserves_checkout_locale(self):
        """Polling must return the same localised gateway link as checkout.

        The payment page reopens the gateway from the polled payload. Before
        ``return_path`` was stored, the status endpoint rebuilt the link without
        a locale, so a student who checked out in Russian was silently sent to
        the Uzbek payment page the first time they pressed "reopen".
        """
        res = self.client.post(
            "/api/payments/checkout/",
            {
                "plan_code": "pro-monthly",
                "provider": "payme",
                "return_path": "/ru/premium/payment/{id}/",
            },
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        payment_id = res.data["id"]

        polled = self.client.get(f"/api/payments/{payment_id}/")
        self.assertEqual(polled.status_code, status.HTTP_200_OK)
        # Same URL as checkout handed out — locale intact.
        self.assertEqual(polled.data["payment_url"], res.data["payment_url"])
        self.assertEqual(
            polled.data["payment_url"], self.client.get(
                f"/api/payments/{payment_id}/"
            ).data["payment_url"]
        )
        receipt = base64.b64decode(
            polled.data["payment_url"][len("https://checkout.paycom.uz/"):]
        ).decode()
        self.assertIn("l=ru", receipt)
        self.assertIn(f"/ru/premium/payment/{payment_id}/", receipt)

    def test_status_endpoint_stable_without_return_path(self):
        """A checkout with no path still resolves to the plain result page."""
        res = self.client.post(
            "/api/payments/checkout/",
            {"plan_code": "pro-monthly", "provider": "payme"},
            format="json",
        )
        payment_id = res.data["id"]
        polled = self.client.get(f"/api/payments/{payment_id}/")
        self.assertEqual(polled.status_code, status.HTTP_200_OK)
        self.assertEqual(polled.data["payment_url"], res.data["payment_url"])
        receipt = base64.b64decode(
            polled.data["payment_url"][len("https://checkout.paycom.uz/"):]
        ).decode()
        self.assertIn("l=uz", receipt)
        self.assertIn(f"c=http://testserver/premium/payment/{payment_id}/", receipt)

    def test_recheckout_from_another_locale_updates_stored_path(self):
        """A reused pending row must follow the student's latest language."""
        first = self.client.post(
            "/api/payments/checkout/",
            {
                "plan_code": "pro-monthly",
                "provider": "payme",
                "return_path": "/ru/premium/payment/{id}/",
            },
            format="json",
        )
        payment_id = first.data["id"]
        self.client.post(
            "/api/payments/checkout/",
            {
                "plan_code": "pro-monthly",
                "provider": "payme",
                "return_path": "/en/premium/payment/{id}/",
            },
            format="json",
        )
        payment = Payment.objects.get(pk=payment_id)
        self.assertEqual(payment.return_path, f"/en/premium/payment/{payment_id}/")

        receipt = base64.b64decode(
            self.client.get(f"/api/payments/{payment_id}/").data["payment_url"][
                len("https://checkout.paycom.uz/"):
            ]
        ).decode()
        self.assertIn("l=en", receipt)
        self.assertIn(f"/en/premium/payment/{payment_id}/", receipt)


@override_settings(**GATEWAY_SETTINGS)
class PaymeWebhookTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="payme-user", password="Passw0rd!", role=User.Role.STUDENT
        )
        self.pro = SubscriptionPlan.objects.create(
            code="pro-monthly",
            tier=SubscriptionPlan.Tier.PRO,
            name_uz="PRO",
            price_uzs=49_000,
            max_sessions_per_day=None,
        )
        self.payment = Payment.objects.create(
            user=self.user,
            plan=self.pro,
            provider=Payment.Provider.PAYME,
            amount_uzs=49_000,
        )

    def _rpc(self, method, params, auth=payme_auth()):
        return self.client.post(
            "/webhooks/payme/",
            data=json.dumps({"method": method, "params": params, "id": 1}),
            content_type="text/json",
            HTTP_AUTHORIZATION=auth,
        )

    def test_missing_credentials_rejected(self):
        res = self._rpc("CheckPerformTransaction", {}, auth="Basic d3Jvbmc=")
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unconfigured_key_fails_closed(self):
        with override_settings(PAYME_KEY=""):
            res = self._rpc("CheckPerformTransaction", {})
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_check_perform_ok(self):
        res = self._rpc(
            "CheckPerformTransaction",
            {"amount": 49_000 * 100, "account": {"payment": str(self.payment.id)}},
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.json()["result"]["allow"])

    def test_check_perform_wrong_amount(self):
        res = self._rpc(
            "CheckPerformTransaction",
            {"amount": 100, "account": {"payment": str(self.payment.id)}},
        )
        self.assertEqual(res.json()["error"]["code"], -31001)

    def test_check_perform_unknown_account(self):
        res = self._rpc(
            "CheckPerformTransaction", {"amount": 100, "account": {"payment": "999"}}
        )
        self.assertEqual(res.json()["error"]["code"], -31050)
        self.assertIn("payment", res.json()["error"]["data"])

    def test_unknown_method(self):
        res = self._rpc("RefundTransaction", {"id": "x"})
        self.assertEqual(res.json()["error"]["code"], -32601)

    def test_full_payment_flow_creates_subscription(self):
        txn = "5305e3bab097f420a62ced0b"
        account = {"payment": str(self.payment.id)}

        created = self._rpc(
            "CreateTransaction",
            {"id": txn, "time": 1_700_000_000_000, "amount": 49_000 * 100, "account": account},
        )
        body = created.json()["result"]
        self.assertEqual(body["state"], 1)
        self.assertEqual(body["transaction"], str(self.payment.id))
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.gateway_ref, txn)

        # Retried CreateTransaction is idempotent.
        again = self._rpc(
            "CreateTransaction",
            {"id": txn, "time": 1_700_000_000_000, "amount": 49_000 * 100, "account": account},
        )
        self.assertEqual(again.json()["result"]["create_time"], body["create_time"])

        performed = self._rpc("PerformTransaction", {"id": txn, "time": 1_700_000_001_000})
        self.assertEqual(performed.json()["result"]["state"], 2)

        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.Status.PAID)
        self.assertIsNotNone(self.payment.subscription)
        self.assertTrue(
            Subscription.objects.filter(user=self.user, plan=self.pro).exists()
        )

        # Repeated PerformTransaction must not stack a second subscription.
        self._rpc("PerformTransaction", {"id": txn, "time": 1_700_000_002_000})
        self.assertEqual(
            Subscription.objects.filter(user=self.user, plan=self.pro).count(), 1
        )

        checked = self._rpc("CheckTransaction", {"id": txn})
        self.assertEqual(checked.json()["result"]["state"], 2)

    def test_cancel_before_perform(self):
        txn = "5305e3bab097f420a62ced0c"
        self.payment.gateway_ref = txn
        self.payment.meta = {"create_time": 1, "state": 1}
        self.payment.save()

        res = self._rpc(
            "CancelTransaction", {"id": txn, "time": 2, "reason": "-31008"}
        )
        self.assertEqual(res.json()["result"]["state"], -1)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.Status.CANCELLED)
        self.assertFalse(Subscription.objects.filter(user=self.user).exists())

    def test_cancel_after_perform_deactivates_subscription(self):
        txn = "5305e3bab097f420a62ced0d"
        now = timezone.now()
        subscription = Subscription.objects.create(
            user=self.user,
            plan=self.pro,
            starts_at=now,
            ends_at=now + timedelta(days=30),
        )
        self.payment.gateway_ref = txn
        self.payment.status = Payment.Status.PAID
        self.payment.subscription = subscription
        self.payment.meta = {"create_time": 1, "perform_time": 3, "state": 2}
        self.payment.save()

        res = self._rpc("CancelTransaction", {"id": txn, "time": 4, "reason": "x"})
        self.assertEqual(res.json()["result"]["state"], -2)
        subscription.refresh_from_db()
        self.assertIsNotNone(subscription.ends_at)

    def test_perform_unknown_transaction(self):
        res = self._rpc("PerformTransaction", {"id": "nope"})
        self.assertEqual(res.json()["error"]["code"], -31003)


@override_settings(**GATEWAY_SETTINGS)
class ClickWebhookTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="click-user", password="Passw0rd!", role=User.Role.STUDENT
        )
        self.pro = SubscriptionPlan.objects.create(
            code="pro-monthly",
            tier=SubscriptionPlan.Tier.PRO,
            name_uz="PRO",
            price_uzs=49_000,
            max_sessions_per_day=None,
        )
        self.payment = Payment.objects.create(
            user=self.user,
            plan=self.pro,
            provider=Payment.Provider.CLICK,
            amount_uzs=49_000,
        )

    def _send(self, **overrides):
        payload = {
            "click_trans_id": "3001234567",
            "service_id": str(CLICK_SERVICE_ID),
            "click_paydoc_id": "16853761",
            "merchant_trans_id": str(self.payment.id),
            "amount": "49000",
            "action": "0",
            "error": "0",
            "error_note": "Ok",
            "sign_time": "2026-05-05 14:30:00",
        }
        payload.update(overrides)
        complete = payload["action"] == "1"
        payload["sign_string"] = overrides.get(
            "sign_string",
            click_sign(
                payload,
                complete=complete,
                merchant_prepare_id=payload.get("merchant_prepare_id", ""),
            ),
        )
        return self.client.post("/webhooks/click/", data=payload)

    def test_bad_signature_rejected(self):
        res = self._send(sign_string="deadbeef")
        self.assertEqual(res.json()["error"], -1)

    def test_prepare_ok(self):
        res = self._send()
        body = res.json()
        self.assertEqual(body["error"], 0)
        self.assertEqual(body["merchant_prepare_id"], str(self.payment.id))
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.meta.get("click_trans_id"), "3001234567")

    def test_prepare_unknown_invoice(self):
        res = self._send(merchant_trans_id="999999")
        self.assertEqual(res.json()["error"], -5)

    def test_prepare_wrong_amount(self):
        res = self._send(amount="999")
        self.assertEqual(res.json()["error"], -2)

    def test_prepare_disabled_without_secret(self):
        with override_settings(CLICK_SECRET_KEY=""):
            res = self._send()
        self.assertEqual(res.json()["error"], -91)

    def test_complete_pays_and_activates(self):
        self._send()
        res = self._send(
            action="1",
            merchant_prepare_id=str(self.payment.id),
            amount="49000",
        )
        body = res.json()
        self.assertEqual(body["error"], 0)
        self.assertEqual(body["merchant_confirm_id"], str(self.payment.id))
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.Status.PAID)
        self.assertTrue(
            Subscription.objects.filter(user=self.user, plan=self.pro).exists()
        )

        # Duplicate complete must be refused, not double-activate.
        dup = self._send(
            action="1",
            merchant_prepare_id=str(self.payment.id),
            amount="49000",
        )
        self.assertEqual(dup.json()["error"], -4)
        self.assertEqual(
            Subscription.objects.filter(user=self.user, plan=self.pro).count(), 1
        )

    def test_complete_unknown_prepare_id(self):
        res = self._send(
            action="1",
            merchant_prepare_id="424242",
            merchant_trans_id="424242",
        )
        self.assertEqual(res.json()["error"], -6)

    def test_complete_with_incoming_error_cancels(self):
        res = self._send(
            action="1",
            merchant_prepare_id=str(self.payment.id),
            error="-5017",
        )
        self.assertEqual(res.json()["error"], -9)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.Status.CANCELLED)

        # Repeating the cancel and confirming afterwards both answer -9.
        again = self._send(
            action="1",
            merchant_prepare_id=str(self.payment.id),
            error="-5017",
        )
        self.assertEqual(again.json()["error"], -9)
        after = self._send(
            action="1",
            merchant_prepare_id=str(self.payment.id),
            error="0",
        )
        self.assertEqual(after.json()["error"], -9)

    def test_complete_amount_mismatch(self):
        res = self._send(
            action="1",
            merchant_prepare_id=str(self.payment.id),
            amount="1000",
        )
        self.assertEqual(res.json()["error"], -2)

    def test_invalid_action(self):
        res = self._send(action="7")
        self.assertEqual(res.json()["error"], -3)


class SubscribePaidRequiresCheckoutTests(APITestCase):
    def setUp(self):
        # SubscribeView shares the "checkout" throttle scope with CheckoutView,
        # and the reused user pk makes both classes hit the same bucket.
        cache.clear()
        self.user = User.objects.create_user(
            username="freekid", password="Passw0rd!", role=User.Role.STUDENT
        )
        SubscriptionPlan.objects.create(
            code="pro-monthly",
            tier=SubscriptionPlan.Tier.PRO,
            name_uz="PRO",
            price_uzs=49_000,
            max_sessions_per_day=None,
        )
        self.client.force_login(self.user)

    def test_paid_plan_returns_checkout_required(self):
        res = self.client.post(
            "/api/premium/subscribe/", {"plan_code": "pro-monthly"}, format="json"
        )
        self.assertEqual(res.status_code, status.HTTP_402_PAYMENT_REQUIRED)
        self.assertTrue(res.data.get("checkout_required"))
