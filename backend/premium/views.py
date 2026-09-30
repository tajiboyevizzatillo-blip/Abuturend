from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import SubscriptionPlan
from .serializers import (
    ActivePlanSerializer,
    SubscribeSerializer,
    SubscriptionPlanSerializer,
)
from .services import (
    activate_plan,
    active_subscription,
    remaining_sessions_today,
)


class PlanListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        plans = SubscriptionPlan.objects.filter(is_active=True)
        return Response(SubscriptionPlanSerializer(plans, many=True).data)


class SubscriptionView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        sub = active_subscription(request.user)
        return Response(
            {
                "is_premium": sub is not None,
                "plan": ActivePlanSerializer(sub).data if sub else None,
                "remaining_sessions_today": remaining_sessions_today(request.user),
            }
        )


class SubscribeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = SubscribeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        plan = serializer.validated_data["plan_code"]

        # The free tier activates instantly. Paid tiers must go through a real
        # gateway: POST /api/payments/checkout/ returns a Payme/Click payment
        # URL and the webhook activates the subscription once money arrives.
        if plan.tier == SubscriptionPlan.Tier.FREE or plan.price_uzs == 0:
            activate_plan(request.user, plan)
        else:
            return Response(
                {
                    "detail": "Pullik tarif uchun to'lov kerak.",
                    "plan_code": plan.code,
                    "price_uzs": plan.price_uzs,
                    "checkout_required": True,
                },
                status=status.HTTP_402_PAYMENT_REQUIRED,
            )
        sub = active_subscription(request.user)
        return Response(
            {
                "is_premium": True,
                "plan": ActivePlanSerializer(sub).data if sub else None,
                "remaining_sessions_today": remaining_sessions_today(request.user),
            },
            status=status.HTTP_201_CREATED,
        )