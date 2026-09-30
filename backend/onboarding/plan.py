"""7-day plan generation.

Deliberately rule-based (no AI, no external call): the wizard answers are few
and the output must be explainable to the student. Rules:

* The plan covers ``min(7, days_left)`` days -- there is no point planning a
  week when the exam is in three days.
* Daily volume comes from ``daily_minutes`` at a fixed pace
  (``MINUTES_PER_QUESTION``), adjusted by the declared level.
* Minutes are split across the selected subjects. A subject the mistakes
  notebook flags as weak gets a bigger share (``WEAK_WEIGHT``).
* Each day is filled round-robin so every subject appears early, capped at
  ``MAX_ITEMS_PER_DAY`` blocks and ``MAX_QUESTIONS_PER_ITEM`` questions (the
  practice API accepts at most 30 questions per session).
"""

from datetime import timedelta

from django.db.models import Count
from django.utils import timezone

from practice.models import PracticeAnswer
from questions.models import Question

PLAN_DAYS = 7
# Minutes a student is assumed to spend per practice question.
MINUTES_PER_QUESTION = 2.0
MAX_ITEMS_PER_DAY = 3
MAX_QUESTIONS_PER_ITEM = 30
MIN_QUESTIONS_PER_ITEM = 5
# Multiplier applied to the whole daily volume by declared level.
LEVEL_FACTORS = {
    "beginner": 0.8,
    "middle": 1.0,
    "high": 1.2,
}
# Weak subjects take this share of the plan instead of an even split.
WEAK_WEIGHT = 1.6
def weak_subject_ids(user, limit=3):
    """Subject ids ordered by unmastered wrong answers (most weak first)."""
    rows = (
        PracticeAnswer.objects.filter(
            session__user=user,
            is_correct=False,
            question__is_active=True,
            question__status=Question.Status.PUBLISHED,
            selected_option__isnull=False,
        )
        .exclude(question_id__in=mastered_question_ids(user))
        .values("question__subject_id")
        .annotate(wrong=Count("id"))
        .order_by("-wrong")[:limit]
    )
    return [r["question__subject_id"] for r in rows if r["question__subject_id"]]


def mastered_question_ids(user):
    """Question ids the student has since answered correctly (in any session)."""
    return list(
        PracticeAnswer.objects.filter(
            session__user=user, is_correct=True, selected_option__isnull=False
        ).values_list("question_id", flat=True)
    )


def daily_question_budget(daily_minutes: int, level: str) -> int:
    factor = LEVEL_FACTORS.get(level, 1.0)
    return max(MIN_QUESTIONS_PER_ITEM, round(daily_minutes / MINUTES_PER_QUESTION * factor))


def _weighted_split(total, weights):
    """Split ``total`` across keys by weight, keeping the remainder deterministic."""
    weight_sum = sum(weights.values())
    if weight_sum <= 0:
        weights = {k: 1 for k in weights}
        weight_sum = len(weights)
    shares = {}
    assigned = 0
    for key, weight in weights.items():
        exact = total * weight / weight_sum
        base = int(exact)
        shares[key] = base
        assigned += base
    # Hand the leftover questions to the heaviest keys, in order.
    leftover = total - assigned
    for key in sorted(weights, key=lambda k: (-weights[k], k))[: max(leftover, 0)]:
        shares[key] += 1
    return shares


def topics_for_subject(subject_id, limit=8):
    """Topic ids of a subject, so consecutive plan days drill different ones."""
    from catalog.models import Topic

    return list(
        Topic.active.filter(subject_id=subject_id)
        .order_by("sort_order", "id")
        .values_list("id", flat=True)[:limit]
    )


def build_plan(profile):
    """Return ``(start_date, days, weak_subject_ids)`` for the given profile."""
    subject_ids = [s.id for s in profile.subjects.all()]
    today = timezone.localdate()
    weak = [sid for sid in weak_subject_ids(profile.user) if sid in subject_ids]
    if not subject_ids:
        return today, [], []

    days_left = profile.days_left
    # No exam date -> always a full week; an imminent exam -> shrink the plan.
    span = PLAN_DAYS if days_left is None else max(1, min(PLAN_DAYS, days_left))
    budget = daily_question_budget(profile.daily_minutes, profile.level)
    weekly_total = budget * span

    weights = {sid: (WEAK_WEIGHT if sid in weak else 1.0) for sid in subject_ids}
    total_questions = _weighted_split(weekly_total, weights)

    # Distribute each subject's questions over the days: round-robin keeps the
    # first day from being dominated by one subject.
    days = [
        {"day": i + 1, "date": (today + timedelta(days=i)).isoformat(), "items": []}
        for i in range(span)
    ]
    subject_topics = {sid: topics_for_subject(sid) for sid in subject_ids}
    for sid in sorted(total_questions, key=lambda s: (-weights[s], s)):
        remaining = total_questions[sid]
        day_index = 0
        while remaining > 0 and day_index < span * MAX_ITEMS_PER_DAY:
            day = days[day_index % span]
            if len(day["items"]) < MAX_ITEMS_PER_DAY and not any(
                item["subject_id"] == sid for item in day["items"]
            ):
                take = min(remaining, MAX_QUESTIONS_PER_ITEM)
                # Rotate topics so the same subject is not drilled on the same
                # topic every single day.
                topic_pool = subject_topics[sid]
                topic_id = topic_pool[(day["day"] - 1) % len(topic_pool)] if topic_pool else None
                day["items"].append(
                    {
                        "subject_id": sid,
                        "topic_id": topic_id,
                        "questions": take,
                        "minutes": round(take * MINUTES_PER_QUESTION),
                    }
                )
                remaining -= take
                day_index += 1
            else:
                day_index += 1

    # Minutes per day should still respect the student's daily budget: the
    # items above are what the student will actually do.
    for day in days:
        day["minutes"] = sum(item["minutes"] for item in day["items"])
        day["questions"] = sum(item["questions"] for item in day["items"])
    return today, days, weak


