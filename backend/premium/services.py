from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .models import Subscription, SubscriptionPlan

FREE_TIER_DAILY_LIMIT = 3

# Distinguishes "caller has no subscription object" from "caller already
# resolved it to None" — passing None must not trigger a second lookup.
_UNSET = object()


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
    # Ordered by remaining coverage rather than row age: renewals stack, so the
    # newest row is not always the one that lasts longest. Ordering by -ends_at
    # (NULLS FIRST, since an open-ended row outlasts everything) keeps the
    # reported plan aligned with the actual entitlement.
    return (
        Subscription.objects.filter(user=user, starts_at__lte=now)
        .filter(Q(ends_at__isnull=True) | Q(ends_at__gt=now))
        .select_related("plan")
        .order_by("-ends_at", "-created_at")
        .first()
    )


def is_premium(user, sub=_UNSET):
    """Paid-tier entitlement.

    Entitlement is about the *tier*, not about merely owning a Subscription
    row. ``POST /api/premium/subscribe/`` creates a real (free) Subscription
    for the free plan, so a "has any row" check made every non-payer premium
    and unlocked the PRO-only features behind weak_skills/practice and the
    radar's paid topic limit.

    ``sub`` lets a caller that already resolved the subscription reuse it
    instead of re-running the query.
    """
    if sub is _UNSET:
        sub = active_subscription(user)
    return sub is not None and sub.plan.tier == SubscriptionPlan.Tier.PRO


def daily_session_limit(user, sub=_UNSET):
    """Sessions a user may start per day; None means unlimited.

    The active plan's own cap is honored for both tiers, since operators
    configure it that way deliberately. The one thing a non-payer may never
    obtain is *unlimited* sessions: ``max_sessions_per_day=NULL`` only means
    "no cap" for the paid tier. On the free tier NULL falls back to the
    platform default rather than granting unlimited use for free.
    """
    if sub is _UNSET:
        sub = active_subscription(user)
    if sub is not None:
        limit = sub.plan.max_sessions_per_day
        if limit is not None:
            return limit
        if sub.plan.tier == SubscriptionPlan.Tier.PRO:
            return None
        return FREE_TIER_DAILY_LIMIT
    return FREE_TIER_DAILY_LIMIT


def sessions_started_today(user):
    """Sessions started today, for the daily quota.

    Abandoned sessions deliberately still count. A session is charged when it
    is created, because creating it already sampled and served its questions —
    the student saw the paper. Refunding the slot on abandon would let a free
    user view unlimited questions without ever answering one, which is exactly
    what the daily limit exists to bound.
    """
    today = timezone.localdate()
    from practice.models import PracticeSession

    return PracticeSession.objects.filter(
        user=user, started_at__date=today
    ).count()


def remaining_sessions_today(user, sub=_UNSET):
    """How many more sessions the user may start today. None = unlimited."""
    if sub is _UNSET:
        sub = active_subscription(user)
    limit = daily_session_limit(user, sub)
    if limit is None:
        return None
    return max(0, limit - sessions_started_today(user))


def can_start_session(user):
    remaining = remaining_sessions_today(user)
    if remaining is None:
        return True, None
    return remaining > 0, remaining