from django.conf import settings
from django.db import models
from django.utils import timezone

from catalog.models import Subject
from universities.models import Direction


class OnboardingProfile(models.Model):
    """Student answers collected by the 3-step wizard.

    One row per user (``OneToOne``): the wizard is idempotent, so re-running it
    updates the same profile instead of piling up duplicates.
    """

    class Level(models.TextChoices):
        BEGINNER = "beginner", "Boshlang'ich"
        MIDDLE = "middle", "O'rta"
        HIGH = "high", "Yuqori"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        related_name="onboarding_profile",
        on_delete=models.CASCADE,
    )
    # nullable: picking a direction is optional (a student may only want to drill).
    direction = models.ForeignKey(
        Direction,
        related_name="onboarding_profiles",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    subjects = models.ManyToManyField(
        Subject, related_name="onboarding_profiles", blank=True
    )
    exam_date = models.DateField(null=True, blank=True, db_index=True)
    daily_minutes = models.PositiveSmallIntegerField(default=60)
    level = models.CharField(
        max_length=16, choices=Level.choices, default=Level.BEGINNER
    )
    completed = models.BooleanField(default=False, db_index=True)
    # Skipping is final for the redirect: the wizard must not nag again.
    skipped = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-id"]
        db_table = "onboarding_profile"

    def __str__(self):
        return f"{self.user} (completed={self.completed})"

    @property
    def days_left(self) -> int:
        """Days until the exam; ``None`` when no date was picked."""
        if not self.exam_date:
            return None
        return (self.exam_date - timezone.localdate()).days

    def needs_onboarding(self) -> bool:
        return not (self.completed or self.skipped)


class OnboardingPlan(models.Model):
    """7-day study plan generated from the profile answers.

    ``days`` is a JSON list of daily entries:
    ``{"day": 1, "date": "2026-09-30", "items": [{"subject_id": 3, "topic_id": 7,
    "questions": 20, "minutes": 25}]}``.
    The list is generated server-side by ``onboarding.plan`` (no AI involved).
    """

    profile = models.ForeignKey(
        OnboardingProfile, related_name="plans", on_delete=models.CASCADE
    )
    start_date = models.DateField()
    days = models.JSONField(default=list)
    # Subjects the mistakes notebook flagged as weak, snapshot at build time so
    # the dashboard can explain *why* the plan is weighted the way it is.
    weak_subject_ids = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-id"]
        db_table = "onboarding_plan"

    def __str__(self):
        return f"Plan for {self.profile_id} from {self.start_date}"

    @property
    def total_questions(self) -> int:
        return sum(
            item["questions"] for day in self.days for item in day.get("items", [])
        )

    def day_for(self, day_number: int):
        for day in self.days:
            if day.get("day") == day_number:
                return day
        return None
