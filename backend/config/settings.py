"""
Django settings for the DTM / Abituriyent Platform backend.

Environment-driven configuration. All secrets and runtime values live in
environment variables (.env in development, real env vars in production).
"""

import os
import sys
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

# ---- Environment helper -------------------------------------------------

def env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name, default=""):
    value = os.environ.get(name, default)
    return [item.strip() for item in value.split(",") if item.strip()]


def env_int(name, default=0):
    try:
        return int(os.environ.get(name, "").strip() or default)
    except ValueError:
        return default


# ---- Core Django settings ------------------------------------------------

SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "django-insecure-local-dev-only-change-me",
)

# Default: DEBUG is on only for the dev server (manage.py runserver). Any real
# server process (gunicorn/uvicorn/docker) starts with DEBUG off unless the
# environment explicitly opts in — a missing DJANGO_DEBUG in production can no
# longer expose traceback pages.
DEBUG = env_bool("DJANGO_DEBUG", "runserver" in sys.argv)

# Default Render domenlari qo'shildi: u yerda boshqa proxy (nginx) yo'q va
# host nomi faqat muhit orqali keladi. VPS uchun DJANGO_ALLOWED_HOSTS
# o'zining domeni bilan cheklanadi.
ALLOWED_HOSTS = env_list(
    "DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,.onrender.com"
)

# Fail closed when a real server process starts without a proper secret.
# manage.py CLI (test/check/migrate/seed) does not serve traffic and runs with
# DEBUG off by default, so it is exempt: local development must not require a
# secret key just to run the test suite.
IS_MANAGE_CLI = Path(sys.argv[0]).name.startswith("manage")

# Every placeholder that has ever shipped in .env.example / docker-compose.
# Guarding only one of them let a second placeholder ("change-me-in-production")
# through and boot production with a publicly known secret. Deny-list them all,
# and require real entropy so an obviously weak value cannot slip in either.
INSECURE_SECRET_KEYS = {
    "django-insecure-local-dev-only-change-me",
    "change-me-in-production",
    "changeme",
    "changethis",
    "secret",
    "secretkey",
    "please-change-me",
    "insecure",
}

if not DEBUG and not IS_MANAGE_CLI:
    if not os.environ.get("DJANGO_SECRET_KEY") or SECRET_KEY in INSECURE_SECRET_KEYS:
        raise ImproperlyConfigured(
            "DJANGO_SECRET_KEY must be set to a strong secret when DJANGO_DEBUG=False."
        )
    if len(SECRET_KEY) < 32:
        raise ImproperlyConfigured(
            "DJANGO_SECRET_KEY is too short; use at least 32 characters "
            "(python -c \"import secrets; print(secrets.token_urlsafe(50))\")."
        )

# Lokal dev server har doim ham 3000-da turmaydi (masalan 3000 boshqa
# loyiha tomonidan egallangan bo'lsa Next.js 3001'ga o'tadi). DEBUG'da bir
# nechcha dev porti ishonchli orginlar ro'yxatiga qo'shiladi, aks holda
# brauzer yuboradigan `Origin: http://localhost:3001` CSRF tekshiruvida
# 403 bilan rad etiladi. Render'da frontend alohida *.onrender.com domenida
# turadi va Next `/api` ni backend'ga proxy qiladi, shuning uchun u ham
# shu ro'yxatda bo'lishi shart — aks holda har bir POST 403 bo'ladi.
# Yuqoridagi qo'shimcha dev portlari faqat DEBUG'da qo'shiladi.
_default_csrf_origins = [
    "http://localhost:3000",
    "http://localhost:8000",
    "https://*.onrender.com",
]
if DEBUG:
    _default_csrf_origins += [f"http://localhost:{p}" for p in range(3001, 3010)]

CSRF_TRUSTED_ORIGINS = env_list(
    "DJANGO_CSRF_TRUSTED_ORIGINS",
    ",".join(_default_csrf_origins),
)

# ---- Application definition ---------------------------------------------

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # third-party
    "rest_framework",
    "django_filters",
    "corsheaders",
    # project apps
    "accounts",
    "catalog",
    "core",
    "questions",
    "practice",
    "premium",
    "payments",
    "gamification",
    "universities",
    "telegrambot",
    "mcpbridge",
    "onboarding",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    # WhiteNoise statik fayllarni (admin, DRF) nginx'siz, Django orqali uzatadi
    # va SecurityMiddleware'dan keyin turishi shart.
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "core.middleware.SecurityHeadersMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# ---- Database -------------------------------------------------------------

# Pooled connections: without CONN_MAX_AGE every request opens a new psycopg
# connection, so a traffic spike burns through Postgres' max_connections
# instead of queueing. 60s + health checks keeps connections warm and drops
# stale ones before Postgres reaps them itself.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB", "abiturend"),
        "USER": os.environ.get("POSTGRES_USER", "abiturend"),
        # No literal fallback: a missing password must fail loudly rather than
        # quietly become the dictionary word "abiturend".
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", ""),
        "HOST": os.environ.get("POSTGRES_HOST", "localhost"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
        "CONN_MAX_AGE": env_int("DJANGO_CONN_MAX_AGE", 60),
        "CONN_HEALTH_CHECKS": True,
        "OPTIONS": {"connect_timeout": env_int("DJANGO_DB_CONNECT_TIMEOUT", 5)},
    }
}

# Render (Heroku uslubi) bitta `DATABASE_URL` beradi: postgres://user:pass@host/db.
# U alohida POSTGRES_* qiymatlardan ustun turadi, chunki ulanish butunlay bitta
# manbadan boshqariladi. SSL faqat uni qo'llab-quvvatlaydigan sxemalar uchun
# talab qilinadi: sqlite OPTIONS ichidagi `sslmode` ni rad etadi, shuning uchun
# "har doim SSL" qoidasi noto'g'ri bo'lardi.
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
if DATABASE_URL:
    _url_scheme = DATABASE_URL.split(":", 1)[0].lower()
    _ssl_supported = _url_scheme in {"postgres", "postgresql", "mysql"}
    DATABASES["default"] = dj_database_url.parse(
        DATABASE_URL,
        conn_max_age=env_int("DJANGO_CONN_MAX_AGE", 60),
        conn_health_checks=True,
        ssl_require=env_bool(
            "DATABASE_URL_SSL_REQUIRE", not DEBUG and _ssl_supported
        ),
    )

# Fallback to SQLite for local development and the test suite. This assignment
# must stay LAST: a second `DATABASES = {...}` further down the file would
# silently clobber it and force Postgres even with DJANGO_USE_SQLITE=1.
if env_bool("DJANGO_USE_SQLITE", False):
    DATABASES["default"] = {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }

# ---- Authentication --------------------------------------------------------

AUTH_USER_MODEL = "accounts.User"

LOGIN_URL = "admin:login"

# ---- Password validation -------------------------------------------------

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# ---- Internationalization -------------------------------------------------

LANGUAGE_CODE = "uz"

LANGUAGES = [
    ("uz", "O'zbek"),
    ("ru", "Русский"),
    ("en", "English"),
]

TIME_ZONE = "Asia/Tashkent"

USE_I18N = True

USE_TZ = True

# ---- Static / Media -------------------------------------------------------

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

# Django 5.1'dan beri STATICFILES_STORAGE o'rniga STORAGES ishlatiladi.
# WhiteNoise `collectstatic` natijasini siqadi (gzip/br) va hashli nomlar
# uchun uzoq muddatli cache qo'yadi, shuning uchun admin/DRF statiki
# nginx'siz (Render) ham to'g'ri va tez uzatiladi.
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
    },
}

# ---- DRF ------------------------------------------------------------------

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "PAGE_SIZE_QUERY_PARAM": "page_size",
    "MAX_PAGE_SIZE": 100,
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.ScopedRateThrottle",
    ],
    # nginx is the only ingress and forwards X-Forwarded-For with
    # $proxy_add_x_forwarded_for, so exactly one proxy sits in front of Django.
    # Without NUM_PROXIES every request shares the proxy's REMOTE_ADDR and the
    # per-scope buckets collapse into one site-wide bucket: 5 registrations per
    # hour for the entire internet. NUM_PROXIES=1 makes DRF read the client IP
    # from the single forwarded hop.
    "NUM_PROXIES": env_int("DJANGO_NUM_PROXIES", 1),
    "DEFAULT_THROTTLE_RATES": {
        "auth": "20/min",
        "register": "5/hour",
        "password": "10/hour",
        "answers": "120/min",
        "checkout": "20/min",
        "public_read": "120/min",
        "stats": "60/min",
    },
}

# ---- CORS ------------------------------------------------------------------

CORS_ALLOWED_ORIGINS = env_list(
    "DJANGO_CORS_ALLOWED_ORIGINS",
    "http://localhost:3000,http://localhost:3001",
)

CORS_ALLOW_CREDENTIALS = True

# ---- Security --------------------------------------------------------------

X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
SECURE_HSTS_SECONDS = env_int("DJANGO_SECURE_HSTS_SECONDS", 0)
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
# Default to Secure unless explicitly disabled. The site is HTTPS-only behind
# nginx; shipping a session cookie over cleartext HTTP is never the intent, and
# an operator who omits these variables should get the safe default rather than
# an insecure one.
SESSION_COOKIE_SECURE = env_bool("DJANGO_SESSION_COOKIE_SECURE", not DEBUG)

CSRF_COOKIE_HTTPONLY = False
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = env_bool("DJANGO_CSRF_COOKIE_SECURE", not DEBUG)

# Only meaningful because nginx overwrites X-Forwarded-Proto with $scheme on
# every proxied request.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# ---- Weak-skill radar (zaif mavzular radari) -------------------------------
# Mavzu bo'yicha aniqlik hisoblanadi va "zaif" deb belgilanadi:
#
#   WEAK_SKILL_MIN_ANSWERS  bitta mavzuni baholash uchun minimal javob soni.
#                          Ostida statistika ishonchsiz bo'ladi, shuning uchun
#                          mavzu "yetarli ma'lumot yo'q" deb belgilanadi va
#                          zaif hisoblanmaydi.
#   WEAK_SKILL_THRESHOLD    zaif deb hisoblash chegarasi (foiz, 0-100).
#   WEAK_SKILL_TOPIC_LIMIT  "eng zaif mavzular" ro'yxatida chiqadigan mavzular.
#   WEAK_SKILL_FREE_TOPICS  bepul tarifda ko'rinadigan zaif mavzular soni.
WEAK_SKILL_MIN_ANSWERS = env_int("WEAK_SKILL_MIN_ANSWERS", 5)
WEAK_SKILL_THRESHOLD = env_int("WEAK_SKILL_THRESHOLD", 60)
WEAK_SKILL_TOPIC_LIMIT = env_int("WEAK_SKILL_TOPIC_LIMIT", 5)
WEAK_SKILL_FREE_TOPICS = env_int("WEAK_SKILL_FREE_TOPICS", 3)
# Zaif mavzulardan avtomatik sessiya yaratishda olinadigan savollar soni.
WEAK_SKILL_PRACTICE_COUNT = env_int("WEAK_SKILL_PRACTICE_COUNT", 20)

# Public leaderboard cache TTL in seconds. Kept short because the ranking is
# recomputed from live session aggregates.
LEADERBOARD_CACHE_SECONDS = env_int("LEADERBOARD_CACHE_SECONDS", 60)

# Zaif-mavzular radari (eng og'ir agregat) cache TTL. Kalit cookie bo'yicha
# har xil, ya'ni boshqa foydalanuvchi javobi hech qachon ko'rinmaydi; LocMem
# workerlar bo'yicha bo'lingani uchun ham xavf yo'q — faqat TTL davomida
# bir xil worker eski javobni qaytarishi mumkin (30 soniya yetarli qisqa).
WEAK_SKILL_CACHE_SECONDS = env_int("WEAK_SKILL_CACHE_SECONDS", 30)

# Telegram botdagi /weak buyrug'i uchun bog'langan hisob (username yoki id).
# Bo'sh yoki topilmasa bot xato bermaydi, faqat "bog'lanmagan" deydi.
TELEGRAM_LINKED_USER = os.environ.get("TELEGRAM_LINKED_USER", "")

# ---- Caching ---------------------------------------------------------------
# Explicit so caching behaviour is a decision rather than an accident. Django
# defaults to LocMemCache, which is per-process: with multiple gunicorn workers
# each process keeps its own copy, so a cached view is sharded and a stale
# entry can outlive a change by up to the timeout. That is acceptable for the
# public leaderboard (recomputed every LEADERBOARD_CACHE_SECONDS) but any
# user-specific data must not be cached without a shared backend.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "abiturend",
        "TIMEOUT": env_int("DJANGO_CACHE_TIMEOUT", 60),
        "KEY_PREFIX": "abiturend",
    }
}

# ---- Logging ---------------------------------------------------------------

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[{asctime}] {levelname} {name} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django.request": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
        "django.security": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
    },
}

# ---- Email -----------------------------------------------------------------

EMAIL_BACKEND = os.environ.get(
    "DJANGO_EMAIL_BACKEND",
    "django.core.mail.backends.console.EmailBackend",
)
EMAIL_HOST = os.environ.get("DJANGO_EMAIL_HOST", "")
EMAIL_PORT = env_int("DJANGO_EMAIL_PORT", 587)
EMAIL_HOST_USER = os.environ.get("DJANGO_EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("DJANGO_EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("DJANGO_EMAIL_USE_TLS", True)
DEFAULT_FROM_EMAIL = os.environ.get(
    "DJANGO_DEFAULT_FROM_EMAIL", "noreply@abituriyent.orgtrace.uz"
)
# Password-reset links point back at the frontend.
FRONTEND_BASE_URL = os.environ.get("FRONTEND_BASE_URL", "http://localhost:3000")

# ---- Telegram bot (admin bildirishnomalar) ---------------------------------

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
TELEGRAM_ALLOWED_CHAT_IDS = env_list("TELEGRAM_ALLOWED_CHAT_IDS", "")
TELEGRAM_WEBHOOK_SECRET = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "")
TELEGRAM_WEBHOOK_HOST = os.environ.get("TELEGRAM_WEBHOOK_HOST", "")

# ---- MCP bridge (mcpbridge) --------------------------------------------------
# The bridge is published over HTTP through nginx and serves the question bank,
# so both keys fail closed: an empty key rejects every request instead of
# allowing anonymous reads.
#
#   MCP_API_KEY       — required for any Streamable HTTP request
#   MCP_ADMIN_API_KEY — additionally required for include_answers=True
MCP_API_KEY = os.environ.get("MCP_API_KEY", "")
MCP_ADMIN_API_KEY = os.environ.get("MCP_ADMIN_API_KEY", "")

# ---- Payments (Payme / Click) ----------------------------------------------
# Ikkalasi ham "fail closed": kalit bo'sh bo'lsa webhook butunlay rad etiladi.
#
#   Payme Merchant API — /webhooks/payme/ (JSON-RPC, Basic auth)
#     PAYME_LOGIN       — kassa logini (ba'zi kabinetlarda "Paycom")
#     PAYME_KEY         — kassa kaliti
#     PAYME_MERCHANT_ID — checkout havolasidagi `m=` (ID yoki alias)
#   Click Shop API — /webhooks/click/ (Prepare/Complete, md5 sign_string)
#     CLICK_SERVICE_ID / CLICK_MERCHANT_ID / CLICK_SECRET_KEY
PAYME_LOGIN = os.environ.get("PAYME_LOGIN", "Paycom")
PAYME_KEY = os.environ.get("PAYME_KEY", "")
PAYME_MERCHANT_ID = os.environ.get("PAYME_MERCHANT_ID", "")
PAYME_CHECKOUT_URL = os.environ.get("PAYME_CHECKOUT_URL", "https://checkout.paycom.uz")
CLICK_SERVICE_ID = env_int("CLICK_SERVICE_ID", 0)
CLICK_MERCHANT_ID = env_int("CLICK_MERCHANT_ID", 0)
CLICK_SECRET_KEY = os.environ.get("CLICK_SECRET_KEY", "")
CLICK_PAY_URL = os.environ.get("CLICK_PAY_URL", "https://my.click.uz/services/pay")