from datetime import timedelta

from django.db.models import Count, Max, Q, Sum
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

    def get(self, request):
        user = request.user
        finished_qs = PracticeSession.objects.filter(
            user=user, status=PracticeSession.Status.FINISHED
        ).select_related("subject", "topic")
        finished = list(finished_qs)

        total_questions = sum(s.question_count for s in finished)
        answered = sum((s.correct_answers + s.incorrect_answers) for s in finished)
        correct = sum(s.correct_answers for s in finished)

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

        # Streak: consecutive days (ending today or yesterday) with a finished session
        dates = {
            timezone.localtime(s.finished_at).date()
            for s in finished
            if s.finished_at is not None
        }
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
        week_answers = (
            PracticeAnswer.objects.filter(
                session__user=user,
                session__status=PracticeSession.Status.FINISHED,
                session__finished_at__date__gte=week_start,
                selected_option__isnull=False,
            )
            .select_related("session")
        )
        for answer in week_answers:
            day = timezone.localtime(answer.answered_at).date()
            if day in activity:
                activity[day][0] += 1
                if answer.is_correct:
                    activity[day][1] += 1
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

        recent = sorted(finished, key=lambda s: s.started_at, reverse=True)[:5]
        recent_sessions = SessionListSerializer(recent, many=True).data

        payload = {
            "total_finished": len(finished),
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

    @staticmethod
    def _mistake_filter(user):
        return PracticeAnswer.objects.filter(
            session__user=user,
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