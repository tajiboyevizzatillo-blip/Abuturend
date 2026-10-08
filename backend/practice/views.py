import random
import sys
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count, F, Q, Sum
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
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

# Exam duration is a server rule, not a client preference. The serializer
# accepts a wide range so the UI can offer preset lengths, but the value is
# clamped here: omitting duration_minutes falls back to the default, and a
# client asking for more than the cap does not get it. Without this clamp a
# request carrying duration_minutes=240 produced a four-hour exam.
DEFAULT_EXAM_MINUTES = 60
MAX_EXAM_MINUTES = 60

# The leaderboard is public, anonymous and aggregation-heavy, so it is cached
# briefly to keep a burst of requests from fanning out into full-table scans.
#
# Disabled while the test suite runs: LocMemCache is process-wide and the
# runner reuses one process for every test, so a cached response from an
# earlier test would be served to a later one that created its own data.
LEADERBOARD_CACHE_SECONDS = (
    0 if "test" in sys.argv else getattr(settings, "LEADERBOARD_CACHE_SECONDS", 60)
)


def sample_questions(queryset, count):
    """Random ``count`` questions without ``ORDER BY RANDOM()``.

    A random sort scans and sorts the whole subject on every request and
    cannot use an index. Sampling the id list in Python gives the same
    uniform draw for banks of any size at the cost of one cheap query.
    """
    ids = list(queryset.values_list("id", flat=True))
    chosen = ids if len(ids) <= count else random.sample(ids, count)
    if not chosen:
        return []
    by_id = {q.id: q for q in queryset.filter(id__in=chosen)}
    return [by_id[i] for i in chosen if i in by_id]


def expire_stale_sessions(user):
    """Finalize exams whose deadline passed while the tab was closed.

    There is no scheduler in this deployment, so a student who closed the tab
    mid-exam would otherwise leave the session ``in_progress`` forever: no
    score, no badges, and a history row that could never be opened. Read paths
    (list/retrieve/report) call this before touching the row, so the report is
    built from the finalized session without any cron job.

    Returns the number of sessions finalized.
    """
    now = timezone.now()
    with transaction.atomic():
        stale = list(
            PracticeSession.objects.select_for_update()
            .filter(
                user=user,
                status=PracticeSession.Status.IN_PROGRESS,
                deadline_at__isnull=False,
                deadline_at__lt=now,
            )
        )
        if not stale:
            return 0
        for session in stale:
            # Scored at the deadline, not "now": everything answered before the
            # clock ran out counts, nothing after it can.
            session.status = PracticeSession.Status.FINISHED
            session.finished_at = session.deadline_at
            session.save(update_fields=["status", "finished_at"])
        # Badge checks are user-level: one pass covers every finalized session.
        from gamification.services import sync_badges

        sync_badges(user)
        return len(stale)


def create_practice_session(
    user, pool, mode, subject=None, topic=None, duration_minutes=None, deadline_at=None
):
    """Create a session and pre-fill it with ``pool`` questions.

    Extracted from ``PracticeSessionViewSet.create`` so other features that
    build a session from a question list (weak-skill practice) reuse the exact
    same code path instead of duplicating session bookkeeping.
    """
    session = PracticeSession.objects.create(
        user=user,
        mode=mode,
        subject=subject,
        topic=topic,
        question_count=len(pool),
        duration_minutes=duration_minutes,
        deadline_at=deadline_at,
    )
    session.answers.bulk_create(
        [PracticeAnswer(session=session, question=q) for q in pool]
    )
    return session


def first_unanswered(session):
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


def session_payload(session, first_question=False):
    """Serialized session for the client (shared by every entry point)."""
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
        "deadline_at": (session.deadline_at.isoformat() if session.deadline_at else None),
        "started_at": session.started_at.isoformat(),
        "finished_at": session.finished_at.isoformat() if session.finished_at else None,
    }
    if first_question:
        answer = first_unanswered(session)
        payload["current_question"] = (
            PracticeQuestionSerializer(answer.question).data if answer else None
        )
    return payload


class LeaderboardView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "public_read"

    # Cached because this is the most expensive read path in the app (three
    # conditional aggregates across every user's sessions) and it is public and
    # anonymous. The cache key must vary on `limit`, which is the only input.
    @method_decorator(cache_page(LEADERBOARD_CACHE_SECONDS))
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
        each subject contributes roughly the same share instead of letting
        a large question bank dominate the paper.

        Ids are read once and sampled in Python: the previous
        per-subject ``ORDER BY RANDOM()`` ran a full scan + sort per subject
        while the caller's row lock (see ``create``) was held.
        """
        groups = {}
        for subject_id, qid in Question.objects.filter(PUBLISHED_ACTIVE).values_list(
            "subject_id", "id"
        ):
            groups.setdefault(subject_id, []).append(qid)
        if not groups:
            return []
        per_subject = -(-requested // len(groups))  # ceil division
        sampled_ids = []
        for subject_id in sorted(groups):
            ids = groups[subject_id]
            sampled_ids.extend(random.sample(ids, min(per_subject, len(ids))))
        random.shuffle(sampled_ids)
        # Ceiling per subject overshoots by at most one round — the paper must
        # still be exactly the requested length.
        sampled_ids = sampled_ids[:requested]
        by_id = {
            q.id: q for q in Question.objects.filter(id__in=sampled_ids)
        }
        return [by_id[qid] for qid in sampled_ids if qid in by_id]

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
                pool = sample_questions(qs, data["question_count"])
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
            # Pool smaller than requested: create_practice_session shrinks the
            # session to the available count so tiny question banks still
            # produce a working exam instead of a hard error.
            duration = data.get("duration_minutes")
            deadline = None
            if data["mode"] == PracticeSession.Mode.EXAM:
                duration = min(
                    duration or DEFAULT_EXAM_MINUTES, MAX_EXAM_MINUTES
                )
                deadline = timezone.now() + timedelta(minutes=duration)
            session = create_practice_session(
                request.user,
                pool,
                mode=data["mode"],
                subject=data.get("subject"),
                topic=data.get("topic"),
                duration_minutes=duration,
                deadline_at=deadline,
            )
        return Response(
            self._session_payload(session, first_question=True),
            status=status.HTTP_201_CREATED,
        )

    def list(self, request, *args, **kwargs):
        # Resolve expired exams before they are rendered as "Jarayonda" rows.
        expire_stale_sessions(request.user)
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, pk=None):
        expire_stale_sessions(request.user)
        session = self.get_object()
        return Response(self._session_payload(session))

    def _first_unanswered(self, session):
        return first_unanswered(session)

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
        return session_payload(session, first_question=first_question)

    @action(detail=True, methods=["get"], url_path="current")
    def current(self, request, pk=None):
        session = self.get_object()
        # Only a live session can hand out its next question.
        if session.status != PracticeSession.Status.IN_PROGRESS:
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
        # A finished/abandoned paper must not hand out its question set again
        # outside the report flow (which also reveals correctness, by design).
        if session.status != PracticeSession.Status.IN_PROGRESS:
            return Response(
                {"detail": "Sessiya yakunlangan."}, status=status.HTTP_409_CONFLICT
            )
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
        # Both FINISHED and ABANDONED are terminal: an abandoned attempt must
        # not keep accepting answers, otherwise the state is cosmetic only.
        if session.status != PracticeSession.Status.IN_PROGRESS:
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
            # Lock the session row: without it two parallel answers both
            # recomputed the counters from a stale read and the last write
            # silently dropped the other's answer from the totals (the score
            # on the finish screen no longer matched the answers).
            locked = PracticeSession.objects.select_for_update().get(pk=session.pk)
            if locked.status != PracticeSession.Status.IN_PROGRESS:
                return Response(
                    {"detail": "Sessiya yakunlangan."}, status=status.HTTP_409_CONFLICT
                )
            if locked.deadline_at and timezone.now() > locked.deadline_at:
                return Response(
                    {
                        "detail": "Vaqt tugadi. Sessiyani yakunlang.",
                        "time_expired": True,
                    },
                    status=status.HTTP_409_CONFLICT,
                )
            answer.selected_option = option
            answer.is_correct = is_correct
            answer.save()
            correct_count = self._recompute_progress(locked)
        if locked.mode == PracticeSession.Mode.EXAM:
            # Exam mode must not echo correctness or a running score: the count
            # itself is an answer oracle when re-answering is allowed.
            return Response(
                {
                    "answered_count": locked.progress_index,
                    "total_count": locked.question_count,
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
            # An abandoned session cannot be finished afterwards either: that
            # would retroactively score an attempt the student walked away from.
            if locked.status != PracticeSession.Status.IN_PROGRESS:
                return Response(
                    {"detail": "Sessiya allaqachon yakunlangan."},
                    status=status.HTTP_409_CONFLICT,
                )
            return self._finalize(request, locked)

    @action(detail=True, methods=["post"], url_path="abandon", url_name="abandon")
    def abandon(self, request, pk=None):
        """Give up on an in-progress session without scoring it.

        Leaving the exam player used to leave the session `in_progress` forever:
        it appeared in the history list as a row that led nowhere, and the
        player could never be resumed. Finishing is not the right verb here —
        the student did not complete the paper, and `finish` would report a
        (deliberately partial) score and unlock badges for it.

        The daily quota slot is still consumed (see premium.services
        .sessions_started_today): the questions were already sampled and served.
        """
        session = self.get_object()
        # Abandoning twice is a no-op conflict, not a second transition.
        if session.status != PracticeSession.Status.IN_PROGRESS:
            return Response(
                {"detail": "Sessiya allaqachon yakunlangan."},
                status=status.HTTP_409_CONFLICT,
            )
        with transaction.atomic():
            locked = PracticeSession.objects.select_for_update().get(pk=session.pk)
            if locked.status != PracticeSession.Status.IN_PROGRESS:
                return Response(
                    {"detail": "Sessiya allaqachon yakunlangan."},
                    status=status.HTTP_409_CONFLICT,
                )
            locked.status = PracticeSession.Status.ABANDONED
            locked.finished_at = timezone.now()
            locked.save(update_fields=["status", "finished_at"])
        return Response({"id": locked.id, "status": locked.status})

    @action(detail=True, methods=["get"], url_path="report", url_name="report")
    def report(self, request, pk=None):
        # A student opening /results right after the deadline gets the finished
        # report instead of a 409: the session is finalized here.
        expire_stale_sessions(request.user)
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
        # select_related: the serializer reads session.finished_at, and without
        # it every row issued its own query (classic N+1 on /certificates).
        qs = (
            Certificate.objects.filter(user=request.user)
            .select_related("session")
            .order_by("-issued_at")
        )
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