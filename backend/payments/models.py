from django.conf import settings
from django.db import models
from django.db.models import Q

from core.models import TimeStampedModel


class Payment(TimeStampedModel):
    """A single checkout attempt for a paid subscription plan.

    The row is created before the user leaves for the gateway and is later
    finalized by the gateway webhook (Payme Merchant API or Click Shop API).
    """

    class Provider(models.TextChoices):
        PAYME = "payme", "Payme"
        CLICK = "click", "Click"

    class Status(models.TextChoices):
        PENDING = "pending", "Kutilmoqda"
        PAID = "paid", "To'langan"
        CANCELLED = "cancelled", "Bekor qilingan"
        FAILED = "failed", "Muvaffaqiyatsiz"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="payments",
        on_delete=models.CASCADE,
    )
    plan = models.ForeignKey(
        "premium.SubscriptionPlan",
        related_name="payments",
        on_delete=models.PROTECT,
    )
    provider = models.CharField(max_length=16, choices=Provider.choices, db_index=True)
    amount_uzs = models.PositiveIntegerField()
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    # Payme transaction id / Click click_trans_id once the gateway sees it.
    gateway_ref = models.CharField(max_length=64, blank=True, default="", db_index=True)
    # Locale-prefixed path the student came from (e.g. "/ru/premium/payment/7/").
    # Snapshotted at checkout so the polling endpoint can rebuild the exact same
    # gateway URL later. Without it the status endpoint regenerated the link
    # without a locale, so reopening the gateway dropped a Russian or English
    # student onto the Uzbek page mid-payment.
    return_path = models.CharField(max_length=128, blank=True, default="")
    # Gateway timestamps (ms) and other protocol state (Payme state, etc).
    meta = models.JSONField(default=dict, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    subscription = models.ForeignKey(
        "premium.Subscription",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="payments",
    )

    objects = models.Manager()

    class Meta:
        ordering = ["-created_at"]
        db_table = "payment"
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "gateway_ref"],
                condition=~Q(gateway_ref=""),
                name="uniq_payment_gateway_ref",
            )
        ]

    def __str__(self):
        return f"#{self.pk} {self.provider} {self.amount_uzs} {self.status}"

    @property
    def is_paid(self):
        return self.status == self.Status.PAID
