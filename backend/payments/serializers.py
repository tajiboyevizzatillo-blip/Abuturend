from rest_framework import serializers

import re

from .models import Payment
from .services import payment_url, provider_configured

# The only redirect we ever hand to the gateway: the payment result page, with
# an optional locale prefix. "{id}" is substituted server-side with the payment
# id (see payments.views.CheckoutView), so the literal is allowed as well.
_RETURN_PATH_RE = re.compile(
    r"^/(?:(?:uz|ru|en)/)?premium/payment/(?:\d+|\{id\})/?$"
)


class CheckoutSerializer(serializers.Serializer):
    plan_code = serializers.CharField()
    provider = serializers.ChoiceField(choices=Payment.Provider.choices)
    return_path = serializers.CharField(required=False, allow_blank=True, default="")

    def validate_plan_code(self, value):
        from premium.models import SubscriptionPlan

        try:
            plan = SubscriptionPlan.objects.get(code=value, is_active=True)
        except SubscriptionPlan.DoesNotExist:
            raise serializers.ValidationError("Bunday aktiv tarif mavjud emas.")
        if plan.price_uzs == 0:
            raise serializers.ValidationError(
                "Bepul tarif uchun to'lov kerak emas: /api/premium/subscribe/"
            )
        return plan

    def validate_provider(self, value):
        if not provider_configured(value):
            raise serializers.ValidationError(
                f"{value} to'lov tizimi sozlanmagan (env konfiguratsiyasini tekshiring)."
            )
        return value

    def validate_return_path(self, value):
        """``return_path`` is sent to the gateway as the post-payment redirect.

        It is therefore an open-redirect vector: browsers normalise ``\\`` to
        ``/``, so a value like ``/\\/evil.com`` contains no ``//`` yet resolves
        to the protocol-relative ``//evil.com`` — a phishing link delivered
        through the payment provider on a legitimate domain. Rather than
        enumerate bypasses, allow-list the one path family we ever send.
        """
        if not value:
            return value
        if not value.startswith("/"):
            raise serializers.ValidationError("return_path / bilan boshlanishi kerak.")
        # Backslashes and control characters are never legitimate here and are
        # the building blocks of the normalisation trick above.
        if "\\" in value or any(ch in value for ch in "\r\n\t\x00"):
            raise serializers.ValidationError("Noto'g'ri return_path.")
        if not _RETURN_PATH_RE.match(value):
            raise serializers.ValidationError("Noto'g'ri return_path.")
        return value


class PaymentSerializer(serializers.ModelSerializer):
    plan_code = serializers.CharField(source="plan.code")
    payment_url = serializers.SerializerMethodField()

    class Meta:
        model = Payment
        fields = [
            "id",
            "plan_code",
            "provider",
            "amount_uzs",
            "status",
            "payment_url",
            "paid_at",
            "created_at",
        ]
        read_only_fields = fields

    def get_payment_url(self, obj):
        if obj.status != Payment.Status.PENDING:
            return None
        return payment_url(
            obj,
            return_url=self.context.get("return_url"),
            lang=self.context.get("lang", "uz"),
        )
