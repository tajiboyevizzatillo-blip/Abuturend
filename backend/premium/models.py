from django.conf import settings
from django.db import models

from core.models import TimeStampedModel


class SubscriptionPlan(TimeStampedModel):
    class Tier(models.TextChoices):
        FREE = "free", "Bepul"
        PRO = "pro", "PRO"

    code = models.CharField(max_length=32, unique=True, db_index=True)
    tier = models.CharField(
        max_length=16, choices=Tier.choices, default=Tier.PRO, db_index=True
    )
    name_uz = models.CharField(max_length=120)
    name_ru = models.CharField(max_length=120, blank=True, default="")
    name_en = models.CharField(max_length=120, blank=True, default="")
    description_uz = models.TextField(blank=True, default="")
    description_ru = models.TextField(blank=True, default="")
    description_en = models.TextField(blank=True, default="")
    price_uzs = models.PositiveIntegerField(default=0)
    duration_days = models.PositiveIntegerField(default=30)
    # None = unlimited sessions; otherwise the daily limit for the tier.
    max_sessions_per_day = models.PositiveIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    sort_order = models.PositiveIntegerField(default=0, db_index=True)

    objects = models.Manager()

    class Meta:
        ordering = ["sort_order", "id"]
        db_table = "premium_plan"

    def __str__(self):
        return self.name_uz

    @property
    def unlimited_sessions(self):
        """Whether this plan really grants uncapped daily sessions.

        Only the paid tier can. `premium.services.daily_session_limit` refuses to
        widen the cap for a free plan, so reporting True here would advertise
        something the backend will not actually grant — and an operator who set
        `max_sessions_per_day = NULL` on a free plan through the admin would see
        the marketing copy silently contradict the enforced limit.
        """
        return (
            self.max_sessions_per_day is None
            and self.tier == SubscriptionPlan.Tier.PRO
        )


class Subscription(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="subscriptions",
        on_delete=models.CASCADE,
    )
    plan = models.ForeignKey(
        SubscriptionPlan, related_name="subscriptions", on_delete=models.PROTECT
    )
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        db_table = "premium_subscription"

    def __str__(self):
        return f"{self.user} -> {self.plan}"

    @property
    def is_active(self):
        from django.utils import timezone

        return self.ends_at is None or self.ends_at > timezone.now()