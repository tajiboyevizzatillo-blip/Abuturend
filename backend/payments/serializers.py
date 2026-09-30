from rest_framework import serializers

from .models import Payment
from .services import payment_url, provider_configured


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
        if value and not value.startswith("/"):
            raise serializers.ValidationError("return_path / bilan boshlanishi kerak.")
        if "//" in value:
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
