"""Zaif mavzular radari — fan va mavzu bo'yicha aniqlik tahlili.

Nima uchun agregat bilan hisoblaymiz (alohida ``TopicStat`` jadvali emas):
javoblar ``PracticeAnswer`` da saqlanadi va har bir so'rovda bitta GROUP BY
bajarish ham eng so'nggi ma'lumotni beradi, ham "yangi javob kelganda
yangilansin" talabini (qo'shimcha jadval + yozuv mantiqi) butunlay olib
tashlaydi — kashf qilingan kashf emas, o'z-o'zidan yangilanadigan hisob.
``Question.topic`` indekslangan (migratsiya ``questions_0014``), shuning uchun
bu so'rovlar indeks ishlatadi va ko'p javobli hisobda ham tez qoladi.

Ishonchlilik qoidasi: mavzuda kamida ``WEAK_SKILL_MIN_ANSWERS`` ta javob
bo'lmasa uni "yetarli ma'lumot yo'q" deb belgilaymiz va zaif hisoblamaymiz —
aks holda bitta javobdan "0%" chiqib, foydalanuvchini chalg'itardi.
"""

import sys

from django.conf import settings
from django.db.models import Case, Count, IntegerField, Max, Sum, Value, When
from django.db.models.functions import TruncDate
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from catalog.models import Subject, Topic
from premium import services as premium_services
from questions.models import Question

from .models import PracticeAnswer, PracticeSession

# Radar/subject reads run GROUP BY scans over the caller's whole answer
# history and are served on every /weak-skills visit and dashboard load.
# Cached per session (the key varies on Cookie), so a stale entry can only
# belong to the student who requested it. Zero while the test suite runs —
# LocMemCache is process-wide and a cached response would leak between tests,
# same reasoning as LEADERBOARD_CACHE_SECONDS in views.py.
WEAK_CACHE_SECONDS = (
    0 if "test" in sys.argv else getattr(settings, "WEAK_SKILL_CACHE_SECONDS", 30)
)


def min_answers():
    """Bir mavzuni baholash uchun minimal javob soni."""
    return max(1, getattr(settings, "WEAK_SKILL_MIN_ANSWERS", 5))


def threshold():
    """Zaif deb hisoblash chegarasi (foiz)."""
    return getattr(settings, "WEAK_SKILL_THRESHOLD", 60)


def free_topic_limit():
    return getattr(settings, "WEAK_SKILL_FREE_TOPICS", 3)


def answered_queryset(user):
    """Faqat haqiqiy javob berilgan, tugallangan sessiyalar.

    ``selected_option`` bo'sh qatorlar — tugallanmagan urinishlar; ularni
    hisobga olinsa aniqlik sun'iy pasayib, zaif mavzular ro'yxati bo'sh
    joylashuvi mumkin edi.
    """
    return (
        PracticeAnswer.objects.filter(
            session__user=user,
            session__status=PracticeSession.Status.FINISHED,
            selected_option__isnull=False,
            question__is_active=True,
            question__status=Question.Status.PUBLISHED,
        ).order_by()
    )


def _accuracy(correct, answered):
    return round((correct or 0) / answered * 100) if answered else 0


def _correct_sum():
    """``SUM(is_correct)`` — Postgres'da boolean yig'ib bo'lmaydi.

    SQLite uchun ``SUM(is_correct)`` ishlaydi, Postgres esa "sum(boolean)"
    xatosini beradi. Shu yerga CASE yozsak, ikkala bazada ham bir xil
    natija va to'g'ri tip chiqadi.
    """
    return Sum(
        Case(When(is_correct=True, then=Value(1)), default=Value(0)),
        output_field=IntegerField(),
    )


def topic_stats(user, subject_id=None, subject_ids=None):
    """Mavzular bo'yicha aniqlik. Bitta agregat so'rovi + nomlarni olish.

    Mavzusiz savollar (``topic_id IS NULL``) alohida qatorga aylanadi va
    ``is_other=True`` bilan qaytariladi — ular uchun o'ylab topilgan mavzu
    yaratilmaydi (boshqa savollar bilan aralashib ketmasligi uchun).

    ``subject_id`` bitta fan, ``subject_ids`` esa bir nechta fan uchun
    (onboarding rejasi faqat tanlangan fanlar statistikasiga muhtoj — SQL
    darajasida filtrlaydi, Python'da emas).
    """
    qs = answered_queryset(user).values(
        "question__topic_id", "question__subject_id"
    ).annotate(
        answered=Count("id"),
        correct=_correct_sum(),
        last_answered_at=Max("answered_at"),
    )
    if subject_id is not None:
        qs = qs.filter(question__subject_id=subject_id)
    elif subject_ids is not None:
        qs = qs.filter(question__subject_id__in=set(subject_ids))

    rows = list(qs)
    topic_ids = {r["question__topic_id"] for r in rows if r["question__topic_id"]}
    topics = {t.id: t for t in Topic.objects.filter(id__in=topic_ids)}
    subject_ids = {r["question__subject_id"] for r in rows if r["question__subject_id"]}
    subjects = {s.id: s for s in Subject.objects.filter(id__in=subject_ids)}

    stats = []
    for r in rows:
        topic_id = r["question__topic_id"]
        topic = topics.get(topic_id) if topic_id else None
        answered = r["answered"]
        accuracy = _accuracy(r["correct"], answered)
        enough = answered >= min_answers()
        stats.append(
            {
                "topic_id": topic_id,
                "topic_name_uz": topic.name_uz if topic else "Boshqa",
                "topic_name_ru": topic.name_ru if topic else "Другое",
                "topic_name_en": topic.name_en if topic else "Other",
                "is_other": topic is None,
                "subject_id": r["question__subject_id"],
                "answered": answered,
                "correct": r["correct"] or 0,
                "wrong": answered - (r["correct"] or 0),
                "accuracy": accuracy,
                "last_answered_at": r["last_answered_at"],
                "enough_data": enough,
                "is_weak": bool(enough and accuracy < threshold()),
            }
        )
    # Zaiflar oldinga, keyin aniqlik bo'yicha; "yetarli ma'lumot yo'q" oxirida.
    stats.sort(key=lambda s: (not s["is_weak"], s["accuracy"], -s["answered"]))
    return stats


def subject_stats(user):
    """Fanlar bo'yicha aniqlik — radar chart o'qlari."""
    rows = (
        answered_queryset(user)
        .values("question__subject_id")
        .annotate(
            answered=Count("id"),
            correct=_correct_sum(),
            last_answered_at=Max("answered_at"),
        )
    )
    ids = [r["question__subject_id"] for r in rows if r["question__subject_id"]]
    subjects = {s.id: s for s in Subject.objects.filter(id__in=ids)}

    result = []
    for r in rows:
        sid = r["question__subject_id"]
        subject = subjects.get(sid) if sid else None
        if subject is None:
            continue
        answered = r["answered"]
        result.append(
            {
                "subject_id": subject.id,
                "slug": subject.slug,
                "subject_name_uz": subject.name_uz,
                "subject_name_ru": subject.name_ru,
                "subject_name_en": subject.name_en,
                "answered": answered,
                "correct": r["correct"] or 0,
                "accuracy": _accuracy(r["correct"], answered),
                "enough_data": answered >= min_answers(),
                "last_answered_at": r["last_answered_at"],
            }
        )
    # Radarda kuchli fan yuqorida chiqishi uchun aniqlik bo'yicha saralanadi.
    result.sort(key=lambda s: (-s["accuracy"], s["subject_id"]))
    return result


def weakest_topics(user, limit=None):
    """Zaif mavzular: yetarli ma'lumotli va chegaradan past aniqlikka ega."""
    limit = limit or getattr(settings, "WEAK_SKILL_TOPIC_LIMIT", 5)
    return [s for s in topic_stats(user) if s["is_weak"]][:limit]


def subject_for_token(token):
    """Fan id yoki slug bilan topiladi (frontend id yuboradi, havola slug)."""
    text = str(token).strip()
    if text.isdigit():
        return Subject.active.filter(id=int(text)).first()
    return Subject.active.filter(slug=text).first()


class FreeSessionLimitReached(Exception):
    """Raised when the daily free-tier session quota is exhausted."""


def create_weak_practice_session(user, pool, subject=None):
    """Create a weak-topic session under the same quota rules as /sessions/.

    The daily-limit check is a read-then-create, so it must run inside a
    transaction with the user row locked — otherwise concurrent requests all
    observe "one slot left" and all create a session, bypassing the quota.
    Sharing one code path with ``PracticeSessionViewSet.create`` keeps the two
    entry points from drifting apart again.
    """
    from django.db import transaction

    from django.contrib.auth import get_user_model

    from .models import PracticeSession

    with transaction.atomic():
        get_user_model().objects.select_for_update().get(pk=user.pk)
        if user.role != user.Role.TEACHER and not user.is_staff:
            allowed, _remaining = premium_services.can_start_session(user)
            if not allowed:
                raise FreeSessionLimitReached
        from .views import create_practice_session

        return create_practice_session(
            user,
            pool,
            mode=PracticeSession.Mode.PRACTICE,
            subject=subject,
        )


class _BaseWeakSkillView(APIView):
    """Faqat o'z statistikasini ko'radigan foydalanuvchilar uchun.

    So'rovda foydalanuvchi id hech qayerda qabul qilinmaydi — doim
    ``request.user`` ishlatiladi, ya'ni boshqa foydalanuvchi ma'lumotiga
    yo'l yo'q (anonim so'rovga DRF 401 beradi).
    """

    permission_classes = [IsAuthenticated]

    @staticmethod
    def rules(is_premium):
        return {
            "threshold": threshold(),
            "min_answers": min_answers(),
            "topic_limit": getattr(settings, "WEAK_SKILL_TOPIC_LIMIT", 5),
            "free_topic_limit": free_topic_limit(),
            "is_premium": is_premium,
        }


def topic_history(user, subject_id, days=14):
    """PRO uchun: mavzular bo'yicha kunlik aniqlik (oxirgi ``days`` kun)."""
    from datetime import timedelta

    from django.utils import timezone

    since = timezone.now() - timedelta(days=days)
    rows = (
        answered_queryset(user)
        .filter(answered_at__gte=since, question__subject_id=subject_id)
        .annotate(day=TruncDate("answered_at"))
        .values("day", "question__topic_id")
        .annotate(answered=Count("id"), correct=_correct_sum())
    )
    topic_ids = {r["question__topic_id"] for r in rows if r["question__topic_id"]}
    topics = {t.id: t for t in Topic.objects.filter(id__in=topic_ids)}
    return [
        {
            "topic_id": r["question__topic_id"],
            "topic_name_uz": (
                topics[r["question__topic_id"]].name_uz
                if r["question__topic_id"]
                else "Boshqa"
            ),
            "day": r["day"].isoformat(),
            "answered": r["answered"],
            "accuracy": _accuracy(r["correct"], r["answered"]),
        }
        for r in rows
    ]


class WeakSkillRadarView(_BaseWeakSkillView):
    """GET /api/weak-skills/ — fanlar radari va eng zaif mavzular."""

    # Each call runs two GROUP BY scans over the caller's whole answer history,
    # so it is rate-limited like the other analytics reads ("stats", 60/min)
    # and cached briefly (see WEAK_CACHE_SECONDS).
    throttle_scope = "stats"

    @method_decorator(cache_page(WEAK_CACHE_SECONDS))
    def get(self, request):
        is_premium = premium_services.is_premium(request.user)
        subjects = subject_stats(request.user)
        weak = weakest_topics(request.user)
        visible = weak if is_premium else weak[: free_topic_limit()]
        payload = self.rules(is_premium)
        payload.update(
            {
                "subjects": subjects,
                "weak_topics": visible,
                # Bepul tarifda yashirilgan mavzular soni — CTA uchun.
                "hidden_weak_topics": max(0, len(weak) - len(visible)),
                "can_practice": is_premium,
                "has_data": bool(subjects),
            }
        )
        return Response(payload)


class WeakSkillSubjectView(_BaseWeakSkillView):
    """GET /api/weak-skills/<fan>/ — tanlangan fan ichidagi mavzular."""

    # Heaviest read in the app: topic stats plus, for PRO, a per-day history
    # aggregate — three scans of the answer history per request.
    throttle_scope = "stats"

    @method_decorator(cache_page(WEAK_CACHE_SECONDS))
    def get(self, request, subject):
        target = subject_for_token(subject)
        if target is None:
            return Response({"detail": "Fan topilmadi."}, status=status.HTTP_404_NOT_FOUND)

        is_premium = premium_services.is_premium(request.user)
        topics = [t for t in topic_stats(request.user, subject_id=target.id) if t["answered"]]
        weak = [t for t in topics if t["is_weak"]]
        shown = weak if is_premium else weak[: free_topic_limit()]
        payload = self.rules(is_premium)
        payload.update(
            {
                "subject": {
                    "subject_id": target.id,
                    "slug": target.slug,
                    "subject_name_uz": target.name_uz,
                    "subject_name_ru": target.name_ru,
                    "subject_name_en": target.name_en,
                },
                "topics": topics,
                "weak_topic_ids": [t["topic_id"] for t in shown if t["topic_id"]],
                "hidden_weak_topics": max(0, len(weak) - len(shown)),
                "can_practice": is_premium,
                "has_data": bool(topics),
            }
        )
        if is_premium:
            payload["history"] = topic_history(request.user, target.id)
        return Response(payload)


class WeakPracticeSerializer(serializers.Serializer):
    """Zaif mavzulardan mashq sessiyasi yaratish so'rovi."""

    subject = serializers.IntegerField(required=False, allow_null=True)
    topic_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        allow_empty=True,
        max_length=10,
    )
    question_count = serializers.IntegerField(
        min_value=1, max_value=30, required=False, allow_null=True
    )

    def validate(self, attrs):
        if not attrs.get("topic_ids") and not attrs.get("subject"):
            raise serializers.ValidationError("Kamida bitta mavzu yoki fan tanlang.")
        return attrs


class WeakSkillPracticeView(_BaseWeakSkillView):
    """POST /api/weak-skills/practice/ — zaif mavzulardan mashq sessiyasi.

    Sessiya mavjud mashq tizimi orqali yaratiladi (javob shakli ham bir xil),
    shuning uchun frontend uchun yangi oynani o'ylab topish kerak emas.
    Bepul tarifga kunlik sessiya limiti ham qo'llaniladi — radar yo'li limitni
    chetlab o'tmasligi kerak.
    """

    throttle_scope = "answers"

    def post(self, request):
        from .views import session_payload

        serializer = WeakPracticeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        is_premium = premium_services.is_premium(request.user)

        topic_ids = list(data.get("topic_ids") or [])
        subject_id = data.get("subject")
        if topic_ids:
            # "Zaif mavzular bo'yicha mashq" — PRO imkoniyati.
            if not is_premium:
                return Response(
                    {
                        "detail": "Zaif mavzular bo'yicha mashq faqat PRO tarifda.",
                        "premium_required": True,
                    },
                    status=status.HTTP_402_PAYMENT_REQUIRED,
                )
            qs = Question.objects.filter(topic_id__in=topic_ids, is_active=True)
            qs = qs.filter(status=Question.Status.PUBLISHED)
        else:
            if not Subject.active.filter(id=subject_id).exists():
                return Response({"detail": "Fan topilmadi."}, status=status.HTTP_404_NOT_FOUND)
            weak_ids = [
                t["topic_id"]
                for t in weakest_topics(request.user, limit=10)
                if t["topic_id"] and t["subject_id"] == subject_id
            ]
            if not weak_ids:
                weak_ids = list(
                    Topic.active.filter(subject_id=subject_id).values_list("id", flat=True)[:10]
                )
            qs = Question.objects.filter(
                topic_id__in=weak_ids, is_active=True, status=Question.Status.PUBLISHED
            )

        count = data.get("question_count") or getattr(settings, "WEAK_SKILL_PRACTICE_COUNT", 20)
        from .views import sample_questions

        pool = sample_questions(qs, count)
        if not pool:
            return Response(
                {"detail": "Bu mavzular uchun savollar mavjud emas."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        subject = None
        if len({q.subject_id for q in pool}) == 1:
            subject = Subject.objects.filter(id=pool[0].subject_id).first()

        # Kunlik limit: radar yo'li ham oddiy /sessions/ bilan bir xil qoida va
        # bir xil atomik blok bilan tekshiriladi.
        try:
            session = create_weak_practice_session(request.user, pool, subject=subject)
        except FreeSessionLimitReached:
            return Response(
                {
                    "detail": (
                        "Kunlik bepul sessiya limiti tugadi. Ertaga qayta urinib "
                        "ko'ring yoki premium tarifga o'ting."
                    ),
                    "premium_required": True,
                },
                status=status.HTTP_402_PAYMENT_REQUIRED,
            )
        return Response(
            session_payload(session, first_question=True), status=status.HTTP_201_CREATED
        )


def weak_skills_text(user, limit=3):
    """Telegram uchun qisqa matn: eng zaif mavzular ro'yxati."""
    topics = weakest_topics(user, limit=limit)
    if not topics:
        return (
            "<b>Zaif mavzular radar</b>\n"
            "Hali yetarli ma'lumot yo'q. Kamida "
            f"{min_answers()} ta javob yig'ish uchun bir nechta mashq bajaring."
        )
    lines = ["<b>Zaif mavzular radar</b>"]
    for i, t in enumerate(topics, start=1):
        name = t["topic_name_uz"]
        lines.append(f"{i}. {name} — {t['accuracy']}% ({t['wrong']} xato)")
    return "\n".join(lines)