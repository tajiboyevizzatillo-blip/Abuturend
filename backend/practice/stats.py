from datetime import timedelta

from django.db.models import Case, Count, IntegerField, Max, Q, Sum, Value, When
from django.db.models.functions import TruncDate
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from catalog.models import Subject, Topic

from gamification.services import level_info
from questions.models import Question

from .models import PracticeAnswer, PracticeSession
from .serializers import SessionListSerializer

PUBLISHED_ACTIVE = Q(is_active=True) & Q(status=Question.Status.PUBLISHED)


class StatsSummaryView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_scope = "stats"

    def get(self, request):
        user = request.user
        finished_qs = PracticeSession.objects.filter(
            user=user, status=PracticeSession.Status.FINISHED
        ).select_related("subject", "topic")

        # Totals and the distinct finished-day list come from the database.
        # This view used to pull every finished session into Python and sum it
        # on each dashboard load, so a power user with thousands of sessions
        # paid that cost on every request.
        totals = finished_qs.aggregate(
            total_questions=Sum("question_count"),
            correct=Sum("correct_answers"),
            incorrect=Sum("incorrect_answers"),
        )
        total_questions = totals["total_questions"] or 0
        correct = totals["correct"] or 0
        answered = correct + (totals["incorrect"] or 0)

        accuracy = round(correct / answered * 100) if answered else 0
        current_score = (
            round(correct / total_questions * 100) if total_questions else 0
        )

        # Subject breakdown — unified exams (subject=None) belong to the
        # totals above, not to a single subject bucket.
        by_subject = (
            finished_qs.filter(subject__isnull=False)
            .values("subject")
            .annotate(
                sessions=Count("id"),
                questions=Sum("question_count"),
                correct=Sum("correct_answers"),
            )
            .order_by("-sessions")
        )
        subject_ids = [row["subject"] for row in by_subject]
        names = {s.id: s for s in Subject.objects.filter(id__in=subject_ids)}
        subject_breakdown = [
            {
                "subject_id": row["subject"],
                "subject_name_uz": names[row["subject"]].name_uz,
                "subject_name_ru": names[row["subject"]].name_ru,
                "subject_name_en": names[row["subject"]].name_en,
                "slug": names[row["subject"]].slug,
                "sessions": row["sessions"],
                "questions": row["questions"],
                "correct": row["correct"],
                "accuracy": round(row["correct"] / row["questions"] * 100)
                if row["questions"]
                else 0,
            }
            for row in by_subject
        ]

        # Streak: consecutive days (ending today or yesterday) with a finished
        # session. Distinct dates are read straight from the database rather
        # than derived from a materialised session list.
        dates = set(
            finished_qs.filter(finished_at__isnull=False)
            .annotate(day=TruncDate("finished_at"))
            .values_list("day", flat=True)
            .distinct()
        )
        today = timezone.localdate()
        streak = 0
        cursor = today
        if cursor not in dates:
            cursor = today - timedelta(days=1)
        while cursor in dates:
            streak += 1
            cursor -= timedelta(days=1)

        # Weekly activity (last 7 days, including today)
        week_start = today - timedelta(days=6)
        activity = {week_start + timedelta(days=i): [0, 0] for i in range(7)}
        # Bucketed in SQL instead of iterating every answer of the week in Python.
        # SUM(is_correct) is not valid on Postgres (boolean), so the CASE form is
        # used, matching practice/weak_skills.py.
        week_rows = (
            PracticeAnswer.objects.filter(
                session__user=user,
                session__status=PracticeSession.Status.FINISHED,
                answered_at__date__gte=week_start,
                selected_option__isnull=False,
            )
            .annotate(day=TruncDate("answered_at"))
            .values("day")
            .annotate(
                answered=Count("id"),
                correct=Sum(
                    Case(
                        When(is_correct=True, then=Value(1)),
                        default=Value(0),
                        output_field=IntegerField(),
                    )
                ),
            )
        )
        for row in week_rows:
            day = row["day"]
            if day in activity:
                activity[day][0] = row["answered"]
                activity[day][1] = row["correct"] or 0
        weekly_activity = [
            {
                "date": day.isoformat(),
                "answered": activity[day][0],
                "correct": activity[day][1],
            }
            for day in sorted(activity)
        ]

        # Weak topics: topics with the most wrong answers
        weak_rows = (
            PracticeAnswer.objects.filter(
                session__user=user,
                session__status=PracticeSession.Status.FINISHED,
                is_correct=False,
                question__topic__isnull=False,
            )
            .values("question__topic")
            .annotate(wrong=Count("id"))
            .order_by("-wrong")[:5]
        )
        topic_ids = [r["question__topic"] for r in weak_rows]
        topic_names = {
            t.id: t for t in Topic.objects.filter(id__in=topic_ids).select_related("subject")
        }
        weak_topics = [
            {
                "topic_id": row["question__topic"],
                "topic_name_uz": topic_names[row["question__topic"]].name_uz,
                "topic_name_ru": topic_names[row["question__topic"]].name_ru,
                "topic_name_en": topic_names[row["question__topic"]].name_en,
                "subject_name_uz": topic_names[row["question__topic"]].subject.name_uz,
                "subject_name_ru": topic_names[row["question__topic"]].subject.name_ru,
                "subject_name_en": topic_names[row["question__topic"]].subject.name_en,
                "wrong": row["wrong"],
            }
            for row in weak_rows
            if row["question__topic"] in topic_names
        ]

        # Only the five most recent sessions are serialized — the full history
        # is not needed here and does not need to be loaded at all.
        recent = list(finished_qs.order_by("-started_at")[:5])
        recent_sessions = SessionListSerializer(recent, many=True).data

        payload = {
            "total_finished": finished_qs.count(),
            "total_questions": total_questions,
            "total_answered": answered,
            "accuracy": accuracy,
            "current_score": current_score,
            "streak": streak,
            "level": level_info(correct * 10),
            "weekly_activity": weekly_activity,
            "subject_breakdown": subject_breakdown,
            "weak_topics": weak_topics,
            "recent_sessions": recent_sessions,
        }
        return Response(payload)


class MistakesView(APIView):
    """Xatolar daftari — every question the student has answered wrongly.

    Sorted by wrong-answer count so the weakest material floats up. ``is_mastered``
    flips to true once the student's latest answer to that question is correct
    (in any later session), so the notebook shrinks as they improve.
    """

    permission_classes = [IsAuthenticated]
    throttle_scope = "stats"

    @staticmethod
    def _mistake_filter(user):
        # Only finished sessions count. An abandoned attempt (crash, closed
        # tab) left answers behind that inflated `total`/`wrong` and could never
        # be cleared, contradicting both this view's own docstring and the
        # sibling weak-skill aggregate, which does filter on FINISHED.
        return PracticeAnswer.objects.filter(
            session__user=user,
            session__status=PracticeSession.Status.FINISHED,
            is_correct=False,
            question__is_active=True,
            question__status=Question.Status.PUBLISHED,
        )

    def get(self, request):
        user = request.user
        rows = (
            self._mistake_filter(user)
            .values("question")
            .annotate(wrong=Count("id"), last_wrong=Max("answered_at"))
            .order_by("-wrong", "-last_wrong")[:50]
        )
        question_ids = [r["question"] for r in rows]

        # Latest answer per question across sessions (higher id = later row;
        # a re-answer updates its row in place). A later correct answer means
        # the student has since mastered that question.
        latest = {}
        for ans in PracticeAnswer.objects.filter(
            session__user=user, question_id__in=question_ids
        ).order_by("id"):
            latest[ans.question_id] = ans.is_correct

        questions = Question.objects.filter(id__in=question_ids).select_related(
            "subject"
        )
        by_id = {q.id: q for q in questions}

        items = []
        for row in rows:
            q = by_id.get(row["question"])
            if q is None:
                continue
            subject = q.subject
            items.append(
                {
                    "question_id": q.id,
                    "text_uz": q.text_uz,
                    "text_ru": q.text_ru,
                    "text_en": q.text_en,
                    "subject_id": subject.id if subject else None,
                    "subject_name_uz": subject.name_uz if subject else None,
                    "subject_name_ru": subject.name_ru if subject else None,
                    "subject_name_en": subject.name_en if subject else None,
                    "wrong": row["wrong"],
                    "last_wrong_at": row["last_wrong"],
                    "is_mastered": bool(latest.get(q.id, False)),
                }
            )
        total = self._mistake_filter(user).values("question").distinct().count()
        return Response({"total": total, "count": len(items), "items": items})