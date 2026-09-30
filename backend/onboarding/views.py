from django.db import transaction
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import OnboardingPlan, OnboardingProfile
from .plan import build_plan
from .serializers import (
    OnboardingPlanSerializer,
    OnboardingProfileSerializer,
    OnboardingSubmitSerializer,
)


class _BaseOnboardingView(APIView):
    """Every endpoint works on the caller's own profile only.

    There is no lookup by id anywhere: an unauthenticated caller gets a 401 and
    an authenticated one only ever sees ``request.user``.
    """

    permission_classes = [IsAuthenticated]

    @staticmethod
    def _get_or_create(request) -> OnboardingProfile:
        profile, _ = OnboardingProfile.objects.get_or_create(user=request.user)
        return profile


class OnboardingView(_BaseOnboardingView):
    """GET ?"/api/onboarding/"" -> current status + profile.

    POST ?"/api/onboarding/"" -> store the wizard answers and build the plan.
    """

    def get(self, request):
        profile = self._get_or_create(request)
        return Response(
            {
                "completed": profile.completed,
                "skipped": profile.skipped,
                "needs_onboarding": profile.needs_onboarding(),
                "profile": OnboardingProfileSerializer(profile).data,
                "has_plan": profile.plans.exists(),
            }
        )

    @transaction.atomic
    def post(self, request):
        serializer = OnboardingSubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        profile, _ = OnboardingProfile.objects.select_for_update().get_or_create(
            user=request.user
        )
        profile.direction = data.get("direction")
        profile.exam_date = data.get("exam_date")
        profile.daily_minutes = data["daily_minutes"]
        profile.level = data["level"]
        # Re-running the wizard is a deliberate "rebuild my plan" action.
        profile.skipped = False
        profile.completed = True
        profile.save()
        profile.subjects.set(data["subjects"])

        start_date, days, weak = build_plan(profile)
        profile.plans.all().delete()
        plan = OnboardingPlan.objects.create(
            profile=profile,
            start_date=start_date,
            days=days,
            weak_subject_ids=weak,
        )

        payload = OnboardingPlanSerializer(plan).data
        _notify_admin(profile)
        return Response(payload, status=status.HTTP_201_CREATED)


class OnboardingPlanView(_BaseOnboardingView):
    """GET ?"/api/onboarding/plan/"" -> the latest plan, or 404 if there is none."""

    def get(self, request):
        profile = self._get_or_create(request)
        plan = profile.plans.order_by("-id").first()
        if plan is None:
            return Response(
                {"detail": "Reja hali yaratilmagan."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(OnboardingPlanSerializer(plan).data)


class OnboardingSkipView(_BaseOnboardingView):
    """POST ?"/api/onboarding/skip/"" -> dismiss the wizard for good."""

    def post(self, request):
        profile, _ = OnboardingProfile.objects.select_for_update().get_or_create(
            user=request.user
        )
        profile.skipped = True
        profile.save(update_fields=["skipped", "updated_at"])
        return Response(OnboardingProfileSerializer(profile).data)


def _notify_admin(profile):
    """Short admin ping after the wizard completes.

    No-op when the bot is unconfigured, runs in a daemon thread (Telegram calls
    block for seconds when the network is slow) and can never break the request:
    the plan is already saved by the time this runs.
    """
    import logging
    import threading

    from telegrambot import services as telegram

    if not telegram.is_configured():
        return

    # Render the text before spawning: the worker thread must not read the
    # profile row, which is still inside the (uncommitted) transaction.
    text = telegram.onboarding_completed_text(profile)

    def _safe():
        try:
            telegram.send_message(text)
        except Exception:
            logging.getLogger(__name__).exception(
                "Onboarding bildirishnomasi yuborilmadi"
            )
        finally:
            # The thread opened its own DB connection; Django never closes those.
            from django.db import close_old_connections

            close_old_connections()

    threading.Thread(target=_safe, daemon=True).start()
