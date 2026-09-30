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


def _status_context(request, payment):
    path = f"/premium/payment/{payment.id}/"
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
        return_path = serializer.validated_data.get("return_path") or ""

        payment = create_checkout(request.user, plan, provider)
        if not return_path:
            return_path = f"/premium/payment/{payment.id}/"
        elif "{id}" in return_path:
            # Frontend sends a locale-prefixed template such as
            # "/ru/premium/payment/{id}/" — substitute the real payment id.
            return_path = return_path.replace("{id}", str(payment.pk))
        if not return_path.endswith("/"):
            return_path += "/"
        return_url = request.build_absolute_uri(return_path)

        data = PaymentSerializer(
            payment,
            context={"return_url": return_url, "lang": _lang_from_path(return_path)},
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
