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
    is_premium,
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
        # One subscription lookup, reused by all three fields: it used to run
        # four queries (active_subscription twice + is_premium + limit).
        sub = active_subscription(request.user)
        return Response(
            {
                "is_premium": is_premium(request.user, sub),
                "plan": ActivePlanSerializer(sub).data if sub else None,
                "remaining_sessions_today": remaining_sessions_today(request.user, sub),
            }
        )


class SubscribeView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_scope = "checkout"

    def post(self, request):
        serializer = SubscribeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        plan = serializer.validated_data["plan_code"]

        # The free tier activates instantly. Paid tiers must go through a real
        # gateway: POST /api/payments/checkout/ returns a Payme/Click payment
        # URL and the webhook activates the subscription once money arrives.
        if plan.tier == SubscriptionPlan.Tier.FREE or plan.price_uzs == 0:
            # Idempotent: activate_plan stacks a new row on top of the current
            # end date, so looping this endpoint built an arbitrarily long
            # chain of subscriptions and made the entitlement effectively
            # permanent. Re-subscribe instead of stacking when already active.
            existing = active_subscription(request.user)
            if existing is not None and existing.plan_id == plan.pk:
                return Response(
                    {
                        "is_premium": is_premium(request.user),
                        "plan": ActivePlanSerializer(existing).data,
                        "remaining_sessions_today": remaining_sessions_today(request.user),
                        "already_subscribed": True,
                    },
                    status=status.HTTP_200_OK,
                )
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
                "is_premium": is_premium(request.user),
                "plan": ActivePlanSerializer(sub).data if sub else None,
                "remaining_sessions_today": remaining_sessions_today(request.user),
                "already_subscribed": False,
            },
            status=status.HTTP_201_CREATED,
        )