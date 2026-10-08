from datetime import timedelta

from django.utils import timezone

from .models import Badge, UserBadge

XP_PER_ANSWER = 10
LEVEL_XP = 200


def user_stats(user):
    """Cheap aggregates used by both badge checks and xp/level math."""
    from practice.models import PracticeAnswer, PracticeSession

    finished = PracticeSession.objects.filter(
        user=user, status=PracticeSession.Status.FINISHED
    )
    answers = PracticeAnswer.objects.filter(
        session__user=user, session__status=PracticeSession.Status.FINISHED
    )

    finished_count = finished.count()
    correct = answers.filter(is_correct=True).count()
    total_answered = answers.filter(selected_option__isnull=False).count()

    # Streak: consecutive days with a finished session, ending today or yesterday.
    # TruncDate+DISTINCT lets the database return one row per active day instead
    # of shipping every finished session's timestamp to Python (the streak walk
    # only needs the day set, and a long-history student had thousands of rows).
    from django.db.models.functions import TruncDate

    today = timezone.localdate()
    dates = set(
        finished.filter(finished_at__isnull=False)
        .annotate(day=TruncDate("finished_at"))
        .values_list("day", flat=True)
        .distinct()
    )
    streak = 0
    cursor = today
    if cursor not in dates:
        cursor = today - timedelta(days=1)
    while cursor in dates:
        streak += 1
        cursor -= timedelta(days=1)

    return {
        "finished_sessions": finished_count,
        "correct_answers": correct,
        "total_answered": total_answered,
        "streak": streak,
        "perfect_sessions": _perfect_sessions(finished),
        "subject_count": finished.values("subject").distinct().count(),
        "exam_sessions": finished.filter(mode=PracticeSession.Mode.EXAM).count(),
        "accuracy": round(correct / total_answered * 100) if total_answered else 0,
        "xp": correct * XP_PER_ANSWER,
    }


def _perfect_sessions(queryset):
    """Sessions where every question was answered and all answers are correct.

    Done as one aggregate query instead of three queries per session (this
    runs on every badges page load and every finished session).
    """
    from django.db.models import Count, F, Q

    return (
        queryset.annotate(
            n_answered=Count(
                "answers", filter=Q(answers__selected_option__isnull=False)
            ),
            n_wrong=Count(
                "answers",
                filter=Q(answers__selected_option__isnull=False)
                & Q(answers__is_correct=False),
            ),
        )
        .filter(n_answered__gt=0, n_answered=F("question_count"), n_wrong=0)
        .count()
    )


def level_info(xp):
    return {
        "xp": xp,
        "level": xp // LEVEL_XP + 1,
        "level_progress": xp % LEVEL_XP,
        "level_progress_pct": round((xp % LEVEL_XP) / LEVEL_XP * 100),
        "next_level_xp": LEVEL_XP,
    }


def _badge_checks(stats):
    return {
        "first-steps": stats["finished_sessions"] >= 1,
        "regular": stats["finished_sessions"] >= 10,
        "marathoner": stats["finished_sessions"] >= 50,
        "streak-3": stats["streak"] >= 3,
        "streak-7": stats["streak"] >= 7,
        "streak-30": stats["streak"] >= 30,
        "sharp-shooter": stats["accuracy"] >= 90 and stats["total_answered"] >= 20,
        "perfect-100": stats["perfect_sessions"] >= 1,
        "centurion": stats["total_answered"] >= 100,
        "scholar-500": stats["total_answered"] >= 500,
        "explorer": stats["subject_count"] >= 5,
        "exam-pro": stats["exam_sessions"] >= 5,
    }


def earned_badge_ids(user):
    return set(
        UserBadge.objects.filter(user=user).values_list("badge_id", flat=True)
    )


def sync_badges(user):
    """Persist newly satisfied badges and return the newly earned list."""
    stats = user_stats(user)
    checks = _badge_checks(stats)
    codes = {code for code, ok in checks.items() if ok}
    badges = {
        b.code: b for b in Badge.objects.filter(code__in=codes, is_active=True)
    }
    new_badges = []
    for code, badge in badges.items():
        _, created = UserBadge.objects.get_or_create(user=user, badge=badge)
        if created:
            new_badges.append(badge)
    return new_badges


def badges_payload(user):
    earned_ids = earned_badge_ids(user)
    badges = Badge.objects.filter(is_active=True)
    payload = []
    for badge in badges:
        payload.append(
            {
                "code": badge.code,
                "name_uz": badge.name_uz,
                "name_ru": badge.name_ru,
                "name_en": badge.name_en,
                "description_uz": badge.description_uz,
                "description_ru": badge.description_ru,
                "description_en": badge.description_en,
                "icon": badge.icon,
                "earned": badge.id in earned_ids,
            }
        )
    return payload