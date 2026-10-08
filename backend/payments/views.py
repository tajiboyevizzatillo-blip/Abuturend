from django.http import Http404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Payment
from .serializers import CheckoutSerializer, PaymentSerializer
from .services import create_checkout

LOCALES = ("uz", "ru", "en")


def _lang_from_path(path):
    head = (path or "").split("/")[1] if path else ""
    return head if head in LOCALES else "uz"


def _normalize_return_path(raw, payment_id):
    """Resolve the frontend's return-path template into a real path.

    The frontend sends a locale-prefixed template such as
    "/ru/premium/payment/{id}/". ``{id}`` is substituted server-side with the
    real payment id, and a missing path falls back to the unprefixed result
    page. Shared by checkout and status so both build the same URL.
    """
    path = raw or ""
    if "{id}" in path:
        path = path.replace("{id}", str(payment_id))
    if not path:
        path = f"/premium/payment/{payment_id}/"
    if not path.endswith("/"):
        path += "/"
    return path


def _status_context(request, payment):
    """Gateway URL context for the polling endpoint.

    Uses the path captured at checkout rather than rebuilding a locale-less
    one, so "reopen the payment page" keeps the student in their language and
    the gateway still sends them back to the right route.
    """
    path = _normalize_return_path(payment.return_path, payment.id)
    return {
        "return_url": request.build_absolute_uri(path),
        "lang": _lang_from_path(path),
    }


class CheckoutView(APIView):
    """Start a checkout for a paid plan via Payme or Click.

    POST /api/payments/checkout/ {plan_code, provider, return_path?}
    -> 201 {payment: {..., payment_url}} — redirect the user to payment_url.
    """

    permission_classes = [IsAuthenticated]
    throttle_scope = "checkout"

    def post(self, request):
        serializer = CheckoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        plan = serializer.validated_data["plan_code"]
        provider = serializer.validated_data["provider"]

        payment = create_checkout(request.user, plan, provider)
        return_path = _normalize_return_path(
            serializer.validated_data.get("return_path"), payment.pk
        )
        # ``create_checkout`` reuses an existing pending row, so a student who
        # starts over from a different language must overwrite the old path.
        if payment.return_path != return_path:
            payment.return_path = return_path
            payment.save(update_fields=["return_path", "updated_at"])
        return_url = request.build_absolute_uri(return_path)

        data = PaymentSerializer(
            payment, context={"return_url": return_url, "lang": _lang_from_path(return_path)}
        ).data
        data["return_url"] = return_url
        return Response(data, status=status.HTTP_201_CREATED)


class PaymentStatusView(APIView):
    """Poll a payment the current user owns."""

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            payment = Payment.objects.select_related("plan").get(
                pk=pk, user=request.user
            )
        except Payment.DoesNotExist:
            raise Http404
        data = PaymentSerializer(
            payment, context=_status_context(request, payment)
        ).data
        return Response(data)
