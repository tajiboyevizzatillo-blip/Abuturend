"""
Django settings for the DTM / Abituriyent Platform backend.

Environment-driven configuration. All secrets and runtime values live in
environment variables (.env in development, real env vars in production).
"""

import os
import sys
from pathlib import Path

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

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")

# Fail closed when a real server process starts without a proper secret.
# manage.py CLI (test/check/migrate/seed) does not serve traffic and runs with
# DEBUG off by default, so it is exempt: local development must not require a
# secret key just to run the test suite.
IS_MANAGE_CLI = Path(sys.argv[0]).name.startswith("manage")

if not DEBUG and not IS_MANAGE_CLI and (
    SECRET_KEY == "django-insecure-local-dev-only-change-me"
    or not os.environ.get("DJANGO_SECRET_KEY")
):
    raise ImproperlyConfigured(
        "DJANGO_SECRET_KEY must be set to a strong secret when DJANGO_DEBUG=False."
    )

CSRF_TRUSTED_ORIGINS = env_list(
    "DJANGO_CSRF_TRUSTED_ORIGINS",
    "http://localhost:3000,http://localhost:8000",
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
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
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

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB", "abiturend"),
        "USER": os.environ.get("POSTGRES_USER", "abiturend"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "abiturend"),
        "HOST": os.environ.get("POSTGRES_HOST", "localhost"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
    }
}

# Fallback to SQLite when no PostgreSQL is reachable during local bootstrap.
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
    "DEFAULT_THROTTLE_RATES": {
        "auth": "20/min",
        "register": "5/hour",
        "password": "10/hour",
        "answers": "120/min",
        "checkout": "20/min",
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
SESSION_COOKIE_SECURE = env_bool("DJANGO_SESSION_COOKIE_SECURE", False)

CSRF_COOKIE_HTTPONLY = False
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = env_bool("DJANGO_CSRF_COOKIE_SECURE", False)

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

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