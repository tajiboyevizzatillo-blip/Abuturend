from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .models import Subscription

FREE_TIER_DAILY_LIMIT = 3


@transaction.atomic
def activate_plan(user, plan):
    """Create a subscription for ``plan`` on top of any active one.

    Renewals stack: a new subscription starts where the current active one
    ends so the user never loses paid days. The user row is locked so two
    concurrent successful payments cannot both stack from the same end date.
    """
    User = get_user_model()
    User.objects.select_for_update().get(pk=user.pk)
    now = timezone.now()
    active = active_subscription(user)
    starts_at = active.ends_at if (active is not None and active.ends_at) else now
    ends_at = starts_at + timedelta(days=plan.duration_days)
    return Subscription.objects.create(
        user=user, plan=plan, starts_at=starts_at, ends_at=ends_at
    )


def active_subscription(user):
    """The most recent active subscription for ``user``, or None.

    ``ends_at`` may be NULL for an admin-created open-ended subscription —
    that counts as active (mirrors ``Subscription.is_active``).
    """
    if not user or not user.is_authenticated:
        return None
    now = timezone.now()
    return (
        Subscription.objects.filter(user=user, starts_at__lte=now)
        .filter(Q(ends_at__isnull=True) | Q(ends_at__gt=now))
        .select_related("plan")
        .order_by("-created_at")
        .first()
    )


def is_premium(user):
    return active_subscription(user) is not None


def daily_session_limit(user):
    """Sessions a user may start per day; None means unlimited."""
    sub = active_subscription(user)
    if sub is not None:
        limit = sub.plan.max_sessions_per_day
        if limit is None:
            return None
        # A paying plan that still carries a cap is honored as-is.
        return limit
    return FREE_TIER_DAILY_LIMIT


def sessions_started_today(user):
    today = timezone.localdate()
    from practice.models import PracticeSession

    return PracticeSession.objects.filter(
        user=user, started_at__date=today
    ).count()


def remaining_sessions_today(user):
    """How many more sessions the user may start today. None = unlimited."""
    limit = daily_session_limit(user)
    if limit is None:
        return None
    return max(0, limit - sessions_started_today(user))


def can_start_session(user):
    remaining = remaining_sessions_today(user)
    if remaining is None:
        return True, None
    return remaining > 0, remaining