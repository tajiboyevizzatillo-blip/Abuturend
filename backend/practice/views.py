import random
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count, F, Q, Sum
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from questions.models import Question, QuestionOption
from questions.serializers import QuestionFullSerializer

from premium import services as premium_services

from .models import Certificate, PracticeAnswer, PracticeSession
from .serializers import (
    CertificateCreateSerializer,
    CertificateSerializer,
    LeaderboardEntrySerializer,
    PracticeAnswerInSerializer,
    PracticeAnswerResultSerializer,
    PracticeQuestionSerializer,
    PracticeStartSerializer,
    SessionListSerializer,
)

User = get_user_model()

PUBLISHED_ACTIVE = Q(is_active=True) & Q(status=Question.Status.PUBLISHED)

# Exam sessions created without an explicit duration get this server-side cap,
# so omitting duration_minutes in the request cannot remove the deadline.
DEFAULT_EXAM_MINUTES = 60


class LeaderboardView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        # ?limit= — the landing widget wants 10, the /leaderboard page up to 50.
        try:
            limit = int(request.query_params.get("limit", 10))
        except (TypeError, ValueError):
            limit = 10
        if limit > 50:
            limit = 50
        elif limit < 1:
            limit = 10  # 0 / negative means "use the default"
        queryset = (
            User.objects.annotate(
                finished_sessions=Count(
                    "practice_sessions",
                    filter=Q(practice_sessions__status=PracticeSession.Status.FINISHED),
                ),
                correct_answers=Sum(
                    "practice_sessions__correct_answers",
                    filter=Q(practice_sessions__status=PracticeSession.Status.FINISHED),
                ),
                total_answered=Sum(
                    F("practice_sessions__correct_answers")
                    + F("practice_sessions__incorrect_answers"),
                    filter=Q(practice_sessions__status=PracticeSession.Status.FINISHED),
                ),
            )
            .filter(finished_sessions__gt=0, is_active=True)
            .exclude(Q(is_staff=True) | Q(is_superuser=True))
            .order_by("-correct_answers", "-total_answered")[:limit]
        )
        for rank, user in enumerate(queryset, start=1):
            user.rank = rank
        data = LeaderboardEntrySerializer(queryset, many=True).data
        return Response(data)


class PracticeSessionViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "head", "options"]
    serializer_class = SessionListSerializer
    filter_backends = [OrderingFilter]
    ordering_fields = ["id", "started_at", "finished_at", "question_count", "correct_answers"]
    ordering = ["-started_at"]
    throttle_scope = "answers"

    def get_queryset(self):
        return PracticeSession.objects.filter(user=self.request.user).select_related(
            "subject", "topic"
        )

    def _unified_pool(self, requested):
        """Sample questions round-robin across every subject.

        A unified exam (umumiy imtihon) must cover the whole syllabus, so
        each subject contributes roughly the same share instead of letting a
        large question bank dominate the paper.
        """
        subject_ids = list(
            Question.objects.filter(PUBLISHED_ACTIVE)
            .values_list("subject_id", flat=True)
            .distinct()
            .order_by("subject_id")
        )
        if not subject_ids:
            return []
        per_subject = -(-requested // len(subject_ids))  # ceil division
        pool = []
        for sid in subject_ids:
            pool.extend(
                Question.objects.filter(PUBLISHED_ACTIVE, subject_id=sid).order_by(
                    "?"
                )[:per_subject]
            )
        random.shuffle(pool)
        return pool[:requested]

    def create(self, request, *args, **kwargs):
        serializer = PracticeStartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        with transaction.atomic():
            # Lock the caller's row so concurrent creates serialize and the
            # daily free-tier check cannot be bypassed (TOCTOU).
            User.objects.select_for_update().get(pk=request.user.pk)
            if request.user.role != User.Role.TEACHER and not request.user.is_staff:
                allowed, remaining = premium_services.can_start_session(request.user)
                if not allowed:
                    return Response(
                        {
                            "detail": (
                                "Kunlik bepul sessiya limiti tugadi. Ertaga qayta urinib "
                                "ko'ring yoki premium tarifga o'ting."
                            ),
                            "premium_required": True,
                            "remaining_sessions_today": 0,
                        },
                        status=status.HTTP_402_PAYMENT_REQUIRED,
                    )
            subject = data.get("subject")
            question_ids = data.get("question_ids")
            if question_ids:
                # Mistakes notebook: exact questions in the requested order
                # (ids were validated as published in the serializer).
                by_id = {
                    q.id: q
                    for q in Question.objects.filter(
                        PUBLISHED_ACTIVE, id__in=question_ids
                    )
                }
                pool = [by_id[i] for i in question_ids if i in by_id]
            elif subject is None:
                pool = self._unified_pool(data["question_count"])
            else:
                qs = Question.objects.filter(PUBLISHED_ACTIVE, subject=subject)
                if data.get("topic"):
                    qs = qs.filter(topic=data["topic"])
                requested = data["question_count"]
                pool = list(qs.order_by("?")[:requested])
            if not pool:
                detail = (
                    "Hozircha testlar mavjud emas."
                    if subject is None
                    else "Ushbu fan bo'yicha hozircha testlar mavjud emas."
                )
                return Response(
                    {"detail": detail},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            # Pool smaller than requested: shrink session to the available count so
            # tiny question banks still produce a working exam instead of a hard error.
            actual_count = len(pool)
            duration = data.get("duration_minutes")
            deadline = None
            if data["mode"] == PracticeSession.Mode.EXAM:
                duration = duration or DEFAULT_EXAM_MINUTES
                deadline = timezone.now() + timedelta(minutes=duration)
            session = PracticeSession.objects.create(
                user=request.user,
                mode=data["mode"],
                subject=data.get("subject"),
                topic=data.get("topic"),
                question_count=actual_count,
                duration_minutes=duration,
                deadline_at=deadline,
            )
            session.answers.bulk_create(
                [PracticeAnswer(session=session, question=q) for q in pool]
            )
        return Response(
            self._session_payload(session, first_question=True),
            status=status.HTTP_201_CREATED,
        )

    def retrieve(self, request, pk=None):
        session = self.get_object()
        return Response(self._session_payload(session))

    def _first_unanswered(self, session):
        """The next question to serve, scoped strictly to this session.

        Looking at ``Question`` and excluding anything answered anywhere leaks
        across sessions: the same question can legitimately sit in two of a
        student's sessions, and answering it in one used to hide it in the other.
        """
        return (
            session.answers.filter(selected_option__isnull=True)
            .select_related("question")
            .order_by("id")
            .first()
        )

    def _recompute_progress(self, session):
        """Recompute the session counters from the answers, both directions.

        Only bumping the counter matching the new answer leaves the other one
        stale as soon as a student changes an answer (wrong -> right).
        """
        answered = session.answers.filter(selected_option__isnull=False)
        correct = answered.filter(is_correct=True).count()
        incorrect = answered.filter(is_correct=False).count()
        session.correct_answers = correct
        session.incorrect_answers = incorrect
        session.progress_index = answered.count()
        session.save(
            update_fields=["correct_answers", "incorrect_answers", "progress_index"]
        )
        return correct

    def _session_payload(self, session, first_question=False):
        # While an exam runs, the running score would let a student binary-search
        # the correct option by re-answering and diffing the counts.
        hide_score = (
            session.mode == PracticeSession.Mode.EXAM
            and session.status != PracticeSession.Status.FINISHED
        )
        payload = {
            "id": session.id,
            "mode": session.mode,
            "subject": session.subject_id,
            "unified": session.subject_id is None
            and session.mode == PracticeSession.Mode.EXAM,
            "topic": session.topic_id,
            "status": session.status,
            "question_count": session.question_count,
            "progress_index": session.progress_index,
            "correct_answers": None if hide_score else session.correct_answers,
            "incorrect_answers": None if hide_score else session.incorrect_answers,
            "duration_minutes": session.duration_minutes,
            "deadline_at": (
                session.deadline_at.isoformat() if session.deadline_at else None
            ),
            "started_at": session.started_at.isoformat(),
            "finished_at": session.finished_at.isoformat() if session.finished_at else None,
        }
        if first_question:
            answer = self._first_unanswered(session)
            payload["current_question"] = (
                PracticeQuestionSerializer(answer.question).data if answer else None
            )
        return payload

    @action(detail=True, methods=["get"], url_path="current")
    def current(self, request, pk=None):
        session = self.get_object()
        if session.status == PracticeSession.Status.FINISHED:
            return Response(
                {"detail": "Sessiya yakunlangan."}, status=status.HTTP_400_BAD_REQUEST
            )
        answer = self._first_unanswered(session)
        return Response(
            {
                "question": (
                    PracticeQuestionSerializer(answer.question).data if answer else None
                ),
                "unanswered_count": session.answers.filter(
                    selected_option__isnull=True
                ).count(),
            }
        )

    @action(detail=True, methods=["get"], url_path="questions", url_name="questions")
    def questions(self, request, pk=None):
        session = self.get_object()
        queryset = (
            Question.objects.filter(practice_answers__session=session)
            .prefetch_related("options")
            .order_by("practice_answers__id")
        )
        serializer = PracticeQuestionSerializer(queryset, many=True)
        return Response({"questions": serializer.data})

    @action(detail=True, methods=["post"], url_path="answer", url_name="answer")
    def answer(self, request, pk=None):
        session = self.get_object()
        if session.status == PracticeSession.Status.FINISHED:
            return Response(
                {"detail": "Sessiya yakunlangan."}, status=status.HTTP_409_CONFLICT
            )
        # Server-side deadline: a patched client that ignores its countdown
        # cannot keep answering after time is up.
        if session.deadline_at and timezone.now() > session.deadline_at:
            return Response(
                {
                    "detail": "Vaqt tugadi. Sessiyani yakunlang.",
                    "time_expired": True,
                },
                status=status.HTTP_409_CONFLICT,
            )
        serializer = PracticeAnswerInSerializer(
            data=request.data, context={"session": session}
        )
        serializer.is_valid(raise_exception=True)
        answer = serializer.validated_data["practice_answer"]
        option_id = serializer.validated_data["option_id"]
        try:
            option = answer.question.options.get(pk=option_id)
        except QuestionOption.DoesNotExist:
            return Response(
                {"option_id": "Noto'g'ri variant."}, status=status.HTTP_400_BAD_REQUEST
            )
        is_correct = option.is_correct
        with transaction.atomic():
            answer.selected_option = option
            answer.is_correct = is_correct
            answer.save()
            correct_count = self._recompute_progress(session)
        if session.mode == PracticeSession.Mode.EXAM:
            # Exam mode must not echo correctness or a running score: the count
            # itself is an answer oracle when re-answering is allowed.
            return Response(
                {
                    "answered_count": session.progress_index,
                    "total_count": session.question_count,
                }
            )
        # A question can legitimately end up without a correct option (bad import,
        # teacher edit). Report that as "no answer key" instead of 500-ing.
        correct_option = answer.question.options.filter(is_correct=True).first()
        result = PracticeAnswerResultSerializer(
            {
                "is_correct": is_correct,
                "correct_option_id": correct_option.id if correct_option else None,
                "explanation_uz": answer.question.explanation_uz,
                "explanation_ru": answer.question.explanation_ru,
                "explanation_en": answer.question.explanation_en,
                "correct_count": correct_count,
                "total_count": session.question_count,
            }
        )
        return Response(result.data)

    def _finalize(self, request, session):
        """Mark the session finished and build its report.

        The caller must hold the row lock (select_for_update) so two concurrent
        finish calls cannot both report success.
        """
        session.status = PracticeSession.Status.FINISHED
        session.finished_at = timezone.now()
        session.save(update_fields=["status", "finished_at"])
        # Gamification: persist any badges the finished session unlocks.
        from gamification.services import sync_badges

        new_badges = sync_badges(request.user)
        report = self._finished_report(session)
        report.data["new_badges"] = [
            {
                "code": b.code,
                "name_uz": b.name_uz,
                "name_ru": b.name_ru,
                "name_en": b.name_en,
                "icon": b.icon,
            }
            for b in new_badges
        ]
        return report

    @action(detail=True, methods=["post"], url_path="finish", url_name="finish")
    def finish(self, request, pk=None):
        session = self.get_object()
        with transaction.atomic():
            locked = PracticeSession.objects.select_for_update().get(pk=session.pk)
            if locked.status == PracticeSession.Status.FINISHED:
                return Response(
                    {"detail": "Sessiya allaqachon yakunlangan."},
                    status=status.HTTP_409_CONFLICT,
                )
            return self._finalize(request, locked)

    @action(detail=True, methods=["get"], url_path="report", url_name="report")
    def report(self, request, pk=None):
        session = self.get_object()
        if session.status != PracticeSession.Status.FINISHED:
            # Until the session is over the report would hand out the answer key
            # for every unanswered question.
            return Response(
                {"detail": "Natijalar sessiya yakunlangach ko'rinadi."},
                status=status.HTTP_409_CONFLICT,
            )
        return self._finished_report(session)

    def _finished_report(self, session):
        answers = (
            session.answers.select_related("question", "selected_option")
            .prefetch_related("question__options")
            .order_by("id")
            .all()
        )
        report = {
            "id": session.id,
            "mode": session.mode,
            "subject": session.subject_id,
            "unified": session.subject_id is None
            and session.mode == PracticeSession.Mode.EXAM,
            "status": session.status,
            "question_count": session.question_count,
            "correct_answers": session.correct_answers,
            "incorrect_answers": session.incorrect_answers,
            "unanswered": session.answers.filter(selected_option__isnull=True).count(),
            "score_percent": round(
                (session.correct_answers / session.question_count) * 100
            )
            if session.question_count
            else 0,
            "started_at": session.started_at.isoformat(),
            "finished_at": (
                session.finished_at.isoformat() if session.finished_at else None
            ),
        }
        questions = []
        for answer in answers:
            q = answer.question
            questions.append(
                {
                    "question": QuestionFullSerializer(q).data,
                    "selected_option_id": answer.selected_option_id,
                    "is_correct": answer.is_correct,
                }
            )
        report["questions"] = questions
        return Response(report)


class CertificateListCreateView(APIView):
    """GET — the current user's certificates; POST — issue one for a finished
    unified exam in the chosen style (international or local)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = Certificate.objects.filter(user=request.user).order_by("-issued_at")
        return Response(CertificateSerializer(qs, many=True).data)

    def post(self, request):
        serializer = CertificateCreateSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        session = serializer.validated_data["session"]
        style = serializer.validated_data["style"]

        percent = (
            round((session.correct_answers / session.question_count) * 100)
            if session.question_count
            else 0
        )
        with transaction.atomic():
            certificate, created = Certificate.objects.get_or_create(
                session=session,
                style=style,
                defaults={
                    "user": request.user,
                    "serial": Certificate.new_serial(),
                    "full_name": (
                        request.user.get_full_name() or request.user.username
                    ),
                    "score_percent": percent,
                    "correct_answers": session.correct_answers,
                    "question_count": session.question_count,
                    "grade": Certificate.band_for(percent),
                    "passed": percent >= 60,
                },
            )
        return Response(
            CertificateSerializer(certificate).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class CertificateVerifyView(APIView):
    """Public authenticity check by serial — no session required, by design:

    a verifier only needs the printed serial (ABT-YYYY-XXXXXX)."""

    permission_classes = [AllowAny]
    throttle_scope = "answers"

    def get(self, request, serial):
        try:
            certificate = Certificate.objects.select_related("session").get(
                serial__iexact=serial
            )
        except Certificate.DoesNotExist:
            return Response(
                {"detail": "Sertifikat topilmadi."}, status=status.HTTP_404_NOT_FOUND
            )
        return Response(CertificateSerializer(certificate).data)