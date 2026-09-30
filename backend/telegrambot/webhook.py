"""Telegram webhook endpoint.

Telegram yangi yangilanishlarni POST sifatida shu endpointga yuboradi.
Xavfsizlik: `X-Telegram-Bot-Api-Secret-Token` header'i bilan himoyalangan
(TELEGRAM_WEBHOOK_SECRET env). Webhook ro'yxatdan o'tkazish:
`python manage.py tg_set_webhook --drop` (yoki deploy paytida avtomatik).
"""

import hmac
import json
import logging

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from . import services

logger = logging.getLogger(__name__)


def _secret_ok(request) -> bool:
    secret = getattr(settings, "TELEGRAM_WEBHOOK_SECRET", "") or ""
    if not secret:
        # Fail closed: without a secret the webhook is unusable in production.
        return bool(getattr(settings, "DEBUG", False))
    header = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "") or ""
    return hmac.compare_digest(header.encode(), secret.encode())


def _authorized(chat_id) -> bool:
    return str(chat_id) in services.get_chat_ids()


def _handle_command(text, chat_id):
    text = (text or "").strip()
    if text == "/start":
        services.send_button_text(
            chat_id,
            services.WELCOME_TEXT,
            [
                [("📊 Statistika", "stats"), ("🏆 Reyting", "top")],
                [("🩺 Holat", "status"), ("📈 7 kun", "trend")],
                [("🎯 Zaif mavzular", "weak"), ("❓ Yordam", "help")],
            ],
        )
    elif text == "/help":
        services.send_message(services.HELP_TEXT, chat_id=chat_id)
    elif text in ("/stats", "stats", "📊 Statistika"):
        services.send_message(services.daily_stats_text(), chat_id=chat_id)
    elif text in ("/top", "top", "🏆 Reyting"):
        services.send_message(services.leaderboard_text(), chat_id=chat_id)
    elif text in ("/status", "status", "🩺 Holat"):
        services.send_message(services.status_text(), chat_id=chat_id)
    elif text in ("/trend", "trend", "📈 7 kun"):
        services.send_message(services.daily_trend_text(), chat_id=chat_id)
    elif text in ("/weak", "weak", "🎯 Zaif mavzular"):
        # Bot hisobga bog'lanmagan bo'lishi mumkin — `weak_skills_text` bu
        # holatda xato bermaydi, tushuntirish qaytaradi.
        services.send_message(services.weak_skills_text(chat_id), chat_id=chat_id)
    elif text == "/id":
        services.send_message(
            f"<b>Chat ID</b>: <code>{chat_id}</code>", chat_id=chat_id
        )
    elif text.startswith("/") and len(text) > 1:
        services.send_message(
            "Noma'lum buyruq. /help bilan tanishing.", chat_id=chat_id
        )
    else:
        services.send_message(
            "Xabar qabul qilindi, rahmat! 📨", chat_id=chat_id
        )


def _handle_callback(query):
    chat = (query.get("message") or {}).get("chat") or {}
    chat_id = str(chat.get("id", ""))
    if not _authorized(chat_id):
        services.answer_callback_query(query.get("id", ""), "Ruxsat yo'q")
        return
    data = str(query.get("data") or "")
    services.answer_callback_query(query.get("id", ""), "Ok ✅")
    _handle_command(data, chat_id)


def _handle_update(update):
    message = update.get("message") or {}
    chat = message.get("chat") or {}
    chat_id = str(chat.get("id", ""))
    if not _authorized(chat_id):
        return
    text = str(message.get("text") or "").strip()
    if not text:
        return
    _handle_command(text, chat_id)


@csrf_exempt
@require_POST
def telegram_webhook(request):
    if not _secret_ok(request):
        logger.warning("Telegram webhook: ruxsatsiz so'rov")
        return JsonResponse({"ok": False, "error": "unauthorized"}, status=401)
    try:
        update = json.loads(request.body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"ok": False, "error": "bad payload"}, status=400)
    try:
        if "callback_query" in update:
            _handle_callback(update["callback_query"])
        else:
            _handle_update(update)
    except Exception:
        logger.exception("Telegram webhook ishlov berish xatosi")
    return JsonResponse({"ok": True})