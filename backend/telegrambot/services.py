"""Telegram bildirishnomalar uchun yordamchi xizmatlar.

Bot token/chat id env orqali sozlanadi (TELEGRAM_BOT_TOKEN,
TELEGRAM_CHAT_ID, TELEGRAM_ALLOWED_CHAT_IDS). Sozlanmagan bo'lsa barcha
chaqiruvlar hech narsa qilmaydi вЂ” rivojlanayotganda bloklanmaydi.
"""

import json
import logging
import time
from datetime import datetime, time
from html import escape as html_escape
from urllib import error as urlerror
from urllib import request as urllib_request

from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from catalog.models import Subject

logger = logging.getLogger(__name__)

_API = "https://api.telegram.org/bot{token}/{method}"
_MAX_ATTEMPTS = 3


def get_bot_token():
    return getattr(settings, "TELEGRAM_BOT_TOKEN", "") or ""


def get_chat_ids():
    ids = list(getattr(settings, "TELEGRAM_ALLOWED_CHAT_IDS", []) or [])
    single = getattr(settings, "TELEGRAM_CHAT_ID", "") or ""
    if single and str(single) not in ids:
        ids.append(str(single))
    return ids


def is_configured():
    return bool(get_bot_token() and get_chat_ids())


def _reply_markup(buttons):
    """Inline tugmalarni (1-4 ustunli qatorlar) Telegram formatiga aylantiradi."""
    return {
        "inline_keyboard": [
            [{"text": text, "callback_data": cb} for text, cb in row]
            for row in buttons
        ]
    }


def send_button_text(chat_id, text, buttons, parse_mode="HTML"):
    """Yozish paneli/klaviaturasiz inline tugmalar bilan xabar yuboradi."""
    return _call(
        "sendMessage",
        {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True,
            "reply_markup": _reply_markup(buttons),
        },
    )


def answer_callback_query(callback_query_id, text=None):
    payload = {"callback_query_id": callback_query_id}
    if text:
        payload["text"] = text
    return _call("answerCallbackQuery", payload)


def _call(method, payload):
    token = get_bot_token()
    if not token:
        return None
    url = _API.format(token=token, method=method)
    data = json.dumps(payload).encode("utf-8")
    req = urllib_request.Request(
        url, data=data, headers={"Content-Type": "application/json"}
    )
    last_error = None
    for attempt in range(_MAX_ATTEMPTS):
        try:
            with urllib_request.urlopen(req, timeout=20) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urlerror.URLError, OSError, ValueError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt < _MAX_ATTEMPTS - 1:
                time.sleep(1.5 * (attempt + 1))
    logger.warning(
        "Telegram API (%s) %s urinishdan keyin muvaffaqiyatsiz: %s",
        method,
        _MAX_ATTEMPTS,
        last_error,
    )
    return None


def send_message(text, parse_mode="HTML", silent=False, chat_id=None):
    """Sozlangan chatlarga xabar yuboradi. Javoblar ro'yxatini qaytaradi."""
    if not is_configured():
        return []
    targets = [chat_id] if chat_id is not None else get_chat_ids()
    results = []
    for cid in targets:
        results.append(
            _call(
                "sendMessage",
                {
                    "chat_id": cid,
                    "text": text,
                    "parse_mode": parse_mode,
                    "disable_web_page_preview": True,
                    "disable_notification": silent,
                },
            )
        )
    return results


def send_typing(chat_id):
    return _call("sendChatAction", {"chat_id": chat_id, "action": "typing"})


def new_user_text(user):
    return (
        "<b>\U0001f389 Yangi foydalanuvchi ro'yxatdan o'tdi</b>\n\n"
        f"\U0001f464 Username: <code>{html_escape(user.username)}</code>\n"
        f"\U0001f3c5 Rol: {html_escape(user.get_role_display())}\n"
        f"\U0001f550 {timezone.localtime(user.date_joined):%d.%m.%Y %H:%M}"
    )


def onboarding_completed_text(profile):
    """Qisqa xabar: abituriyent onboarding wizard'ni tugatdi va reja oldi."""
    user = profile.user
    plan = profile.plans.order_by("-id").first()
    name = user.get_full_name() or user.username
    direction = profile.direction.name_uz if profile.direction_id else "belgilanmagan"
    subjects = ", ".join(s.name_uz for s in profile.subjects.all()[:4])
    if profile.subjects.count() > 4:
        subjects += "..."
    level_labels = {"beginner": "boshlang'ich", "middle": "o'rta", "high": "yuqori"}
    level = level_labels.get(profile.level, profile.level)
    exam = profile.exam_date.isoformat() if profile.exam_date else "belgilanmagan"
    if plan is None:
        plan_line = ""
    else:
        weak_names = [
            s.name_uz for s in Subject.objects.filter(id__in=plan.weak_subject_ids or [])
        ]
        weak_text = ", ".join(weak_names) if weak_names else "yo'q"
        plan_line = (
            f"\n\U0001f4d8 Reja: <b>{plan.total_questions}</b> ta savol / "
            f"{len(plan.days)} kun"
            f"\n\U0001f6a8 Zaif fanlar: {html_escape(weak_text)}"
        )
    return (
        "<b>\U0001f9ed Onboarding tugallandi</b>\n\n"
        f"\U0001f464 Foydalanuvchi: <b>{html_escape(name)}</b>\n"
        f"\U0001f3af Yo'nalish: {html_escape(direction)}\n"
        f"\U0001f4da Fanlar: {html_escape(subjects or '-')}\n"
        f"\U0001f4c5 Imtihon: <b>{exam}</b>\n"
        f"\u23f1 Kunlik vaqt: <b>{profile.daily_minutes}</b> daqiqa\n"
        f"\U0001f3c3 Daraja: {html_escape(level)}"
        f"{plan_line}"
    )


def send_onboarding_completed(profile):
    return send_message(onboarding_completed_text(profile))


def question_submitted_text(question):
    author = question.created_by
    subject = question.subject.name_uz if question.subject_id else "вЂ”"
    snippet = (question.text_uz or "").strip().replace("\n", " ")[:120]
    author_name = author.get_full_name() if author else "вЂ”"
    if not author_name.strip():
        author_name = author.username if author else "вЂ”"
    return (
        "<b>\U0001f9d1\u200d\U0001f4bb O'qituvchi yangi savol qo'shdi</b>\n\n"
        f"\U0001f4da Fan: <b>{html_escape(subject)}</b>\n"
        f"\U0001f4dd Savol: {html_escape(snippet) or 'вЂ”'}\n"
        f"\U0001f464 Muallif: {html_escape(author_name)}\n"
        f"\U0001f550 {timezone.localtime(question.created_at):%d.%m.%Y %H:%M}\n"
        "\u23f3 Holati: tekshiruvda"
    )


def send_new_user(user):
    send_message(new_user_text(user))


def send_question_submitted(question):
    send_message(question_submitted_text(question))


def daily_stats_text():
    from django.contrib.auth import get_user_model

    from practice.models import PracticeAnswer, PracticeSession
    from questions.models import Question

    User = get_user_model()
    today = timezone.localdate()
    day_start = timezone.make_aware(
        datetime.combine(today, time.min), timezone.get_current_timezone()
    )
    day_end = day_start + timezone.timedelta(days=1)

    total_users = User.objects.count()
    users_today = User.objects.filter(
        date_joined__gte=day_start, date_joined__lt=day_end
    ).count()
    total_questions = Question.objects.count()
    published = Question.objects.filter(status=Question.Status.PUBLISHED).count()
    pending = Question.objects.filter(status=Question.Status.DRAFT).count()
    sessions_today = PracticeSession.objects.filter(
        started_at__gte=day_start, started_at__lt=day_end
    ).count()
    answers_today = PracticeAnswer.objects.filter(
        answered_at__gte=day_start, answered_at__lt=day_end
    ).count()
    correct_today = PracticeAnswer.objects.filter(
        answered_at__gte=day_start,
        answered_at__lt=day_end,
        is_correct=True,
    ).count()
    accuracy = (
        round((correct_today / answers_today) * 100) if answers_today else None
    )
    accuracy_text = f"{accuracy}%" if accuracy is not None else "вЂ”"

    return (
        "<b>\U0001f4ca Abiturend вЂ” statistika</b>\n"
        f"\U0001f5d3\ufe0f {today:%d.%m.%Y}\n\n"
        f"\U0001f465 Jami foydalanuvchilar: <b>{total_users}</b>\n"
        f"\U0001f195 Bugun ro'yxatdan o'tganlar: <b>{users_today}</b>\n"
        f"\U0001f4dd Jami savollar: <b>{total_questions}</b>\n"
        f"\U0001f4cc Chop etilgan: <b>{published}</b>\n"
        f"\u23f3 Tekshiruvda: <b>{pending}</b>\n\n"
        f"\U0001f4c8 Bugungi faollik:\n"
        f"\u2022 Sessiyalar: <b>{sessions_today}</b>\n"
        f"\u2022 Javoblar: <b>{answers_today}</b>\n"
        f"\u2022 To'g'riligi: <b>{accuracy_text}</b>"
    )


def send_daily_stats():
    send_message(daily_stats_text())


def leaderboard_text(limit=10):
    """Top abituriyentlar вЂ” to'g'ri javoblar soni bo'yicha."""
    from django.contrib.auth import get_user_model
    from django.db.models import Count, F, Sum

    from practice.models import PracticeSession

    User = get_user_model()
    qs = (
        User.objects.annotate(
            finished=Count(
                "practice_sessions",
                filter=Q(practice_sessions__status=PracticeSession.Status.FINISHED),
            ),
            correct=Sum(
                "practice_sessions__correct_answers",
                filter=Q(practice_sessions__status=PracticeSession.Status.FINISHED),
            ),
            total=Sum(
                F("practice_sessions__correct_answers")
                + F("practice_sessions__incorrect_answers"),
                filter=Q(practice_sessions__status=PracticeSession.Status.FINISHED),
            ),
        )
        .filter(finished__gt=0, is_active=True)
        .exclude(Q(is_staff=True) | Q(is_superuser=True))
        .order_by("-correct", "-total")[:limit]
    )
    if not qs.exists():
        return "<b>\U0001f3c5 Reyting</b>\n\nHozircha natijalar mavjud emas. Abiturientlar test topshirishni boshlashlari kerak!"
    lines = ["<b>\U0001f3c5 Abiturend вЂ” TOP bilimdonlar</b>", ""]
    medals = ["\U0001f947", "\U0001f948", "\U0001f949"]
    for i, user in enumerate(qs, start=1):
        name = user.first_name or user.username
        badge = f'{medals[i - 1]} ' if i <= 3 else f"{i}. "
        acc = round(user.correct * 100 / user.total) if user.total else 0
        lines.append(
            f"{badge}<b>{html_escape(name)}</b>\n"
            f"   \u2705 {user.correct} to'g'ri В· \U0001f4c4 {user.finished} ta test В· "
            f"\U0001f3af {acc}% aniqlik"
        )
    lines.append("")
    lines.append("Test topshirib o'z o'rningni egalla! \u2728")
    return "\n".join(lines)


def status_text():
    """Platforma holati вЂ” savollar, foydalanuvchilar, sog'lomlik."""
    from django.contrib.auth import get_user_model

    from questions.models import Question

    User = get_user_model()
    pending = Question.objects.filter(status=Question.Status.DRAFT).count()
    published = Question.objects.filter(
        status=Question.Status.PUBLISHED
    ).count()
    return (
        "<b>\U0001f9fe Abiturend вЂ” holat</b>\n\n"
        f"\U0001f4dd Savollar: <b>{Question.objects.count()}</b>\n"
        f"   \u2705 Chop etilgan: <b>{published}</b>\n"
        f"   \u23f3 Tekshiruvda: <b>{pending}</b>\n"
        f"\U0001f465 Foydalanuvchilar: <b>{User.objects.count()}</b>\n"
        f"\U0001f3c6 Test topshirganlar: <b>{User.objects.filter(practice_sessions__isnull=False).distinct().count()}</b>\n"
        "\u26a1 Platforma: <b>\u2705 faol</b>"
    )


def daily_trend_text():
    """So'nggi 7 kun aktivligi вЂ” sessiyalar va to'g'ri javob ulushi."""
    from datetime import timedelta

    from practice.models import PracticeAnswer, PracticeSession

    today = timezone.localdate()
    start = timezone.make_aware(
        datetime.combine(today - timedelta(days=6), time.min),
        timezone.get_current_timezone(),
    )
    rows = []
    for i in range(7):
        day = today - timedelta(days=6 - i)
        ds = timezone.make_aware(
            datetime.combine(day, time.min), timezone.get_current_timezone()
        )
        de = ds + timezone.timedelta(days=1)
        sessions = PracticeSession.objects.filter(
            started_at__gte=ds, started_at__lt=de
        ).count()
        answers = PracticeAnswer.objects.filter(
            answered_at__gte=ds, answered_at__lt=de
        ).count()
        correct = PracticeAnswer.objects.filter(
            answered_at__gte=ds,
            answered_at__lt=de,
            is_correct=True,
        ).count()
        acc = round((correct / answers) * 100) if answers else None
        row = "рџџ©" if sessions else "в¬њ"
        rows.append(
            f"{day:%a} {row} В· {sessions} sessiya В· "
            f"{('%.0f%%' % acc) if acc is not None else 'вЂ”'} to'g'ri"
        )
    return (
        "<b>рџ“€ So'nggi 7 kun faolligi</b>\n"
        f"{today:%d.%m.%Y} holatiga\n\n"
        + "\n".join(rows)
    )

def weak_skills_text(chat_id=None):
    """/weak вЂ” bog'langan hisobning eng zaif 3 mavzusi.

    Bot hisoblar bilan bog'lanmagan (chat_id -> user bog'lanishi yo'q), shu
    sababli bitta aniq hisob `TELEGRAM_LINKED_USER` orqali ko'rsatiladi. Bot
    sozlanmagan yoki hisob topilmasa xato bermaydi вЂ” faqat tushuntirish
    qaytaradi, webhook esa har doim 200 qaytaradi.
    """
    from django.conf import settings as django_settings
    from django.contrib.auth import get_user_model

    linked = (getattr(django_settings, "TELEGRAM_LINKED_USER", "") or "").strip()
    if not linked:
        return (
            "<b>Zaif mavzular radar</b>\n"
            "Bot hali hisobga bog'lanmagan. Administrator "
            "TELEGRAM_LINKED_USER ni sozlamasida ko'rsatishi kerak."
        )
    User = get_user_model()
    user = (
        User.objects.filter(username=linked).first()
        or (User.objects.filter(pk=linked).first() if linked.isdigit() else None)
    )
    if user is None:
        return (
            "<b>Zaif mavzular radar</b>\n"
            "Bog'langan hisob topilmadi. Administrator sozlamani tekshirsin."
        )

    from practice.weak_skills import weak_skills_text as render

    return render(user, limit=3)


WELCOME_TEXT = (
    "<b>рџ¤– Abiturend bot</b>\n\n"
    "Assalomu alaykum! Men Abiturend platformasi botiman.\n"
    "Quyidagi tugmalar yoki buyruqlar orqali boshqaring:\n\n"
    "вЂў /stats вЂ” kunlik statistika\n"
    "вЂў /top вЂ” TOP-10 abituriyentlar reytingi\n"
    "вЂў /status вЂ” platforma holati\n"
    "вЂў /trend вЂ” so'nggi 7 kun faolligi\n"
    "вЂў /weak вЂ” eng zaif mavzular\n"
    "вЂў /help вЂ” barcha buyruqlar ro'yxati\n"
    "вЂў /id вЂ” chat ID ko'rsatish"
)


HELP_TEXT = (
    "<b>рџ¤– Abiturend bot вЂ” yordam</b>\n\n"
    "<b>Buyruqlar:</b>\n"
    "вЂў /start вЂ” asosiy menyu\n"
    "вЂў /stats вЂ” kunlik statistika (foydalanuvchilar, savollar, faollik)\n"
    "вЂў /top вЂ” TOP-10 bilimdonlar reytingi\n"
    "вЂў /status вЂ” platforma holati (savollar, foydalanuvchilar)\n"
    "вЂў /trend вЂ” so'nggi 7 kun faolligi\n"
    "вЂў /weak вЂ” eng zaif 3 mavzu (aniqlik radar)\n"
    "вЂў /id вЂ” joriy chat ID\n"
    "вЂў /help вЂ” bu xabar\n\n"
    "<b>Avtomatik bildirishnomalar:</b>\n"
    "вЂў Yangi foydalanuvchi ro'yxatdan o'tsa\n"
    "вЂў O'qituvchi yangi savol qo'shsa\n"
    "вЂў Kunlik statistika (cron orqali)\n\n"
    "Botga savol yuborilsa вЂ” admin sifatida qabul qilinadi va "
    "tegishli bo'limga yo'naltiriladi."
)