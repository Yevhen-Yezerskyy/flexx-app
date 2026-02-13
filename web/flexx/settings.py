# FILE: web/flexx/settings.py  (обновлено — 2026-02-13)
# PURPOSE: Нормальный DB-конфиг через env (дефолты под compose), логирование через root + WatchedFileHandler, reset-link TTL = 7 дней.

from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _env_bool(name: str, default: bool = False) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    v = v.strip().lower()
    return v in ("1", "true", "yes", "y", "on")


def _env_csv(name: str, default: list[str]) -> list[str]:
    v = os.getenv(name)
    if not v:
        return default
    return [x.strip() for x in v.split(",") if x.strip()]


SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-only-change-me")
DEBUG = _env_bool("DJANGO_DEBUG", default=False)

ALLOWED_HOSTS = _env_csv(
    "DJANGO_ALLOWED_HOSTS",
    default=[
        "vertrag.flexxlager.de",
        "dev-vertrag.flexxlager.de",
    ],
)

CSRF_TRUSTED_ORIGINS = _env_csv(
    "DJANGO_CSRF_TRUSTED_ORIGINS",
    default=[
        "https://vertrag.flexxlager.de",
        "https://dev-vertrag.flexxlager.de",
        "http://vertrag.flexxlager.de",
        "http://dev-vertrag.flexxlager.de",
    ],
)

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "app_users",
]

AUTH_USER_MODEL = "app_users.FlexxUser"

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "flexx.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    }
]

WSGI_APPLICATION = "flexx.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("POSTGRES_DB", "flexx"),
        "USER": os.getenv("POSTGRES_USER", "flexx"),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD", "flexx_passwd"),
        "HOST": os.getenv("POSTGRES_HOST", "postgres"),
        "PORT": os.getenv("POSTGRES_PORT", "5432"),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "de"
TIME_ZONE = "Europe/Berlin"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = "/app/static"
STATICFILES_DIRS = [BASE_DIR / "static"]

MEDIA_URL = "/media/"
MEDIA_ROOT = "/app/media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# reset/set password links: 7 days
PASSWORD_RESET_TIMEOUT = 60 * 60 * 24 * 7

# ---------------- LOGGING ----------------

LOG_DIR = Path(os.getenv("FLEXX_LOG_DIR", "/app/logs"))
LOG_LEVEL = os.getenv("FLEXX_LOG_LEVEL", "INFO").upper()

try:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
except Exception:
    pass

WEB_LOG_FILE = str(LOG_DIR / os.getenv("FLEXX_WEB_LOG_FILE", "web.log"))

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "std": {"format": "%(asctime)s %(levelname)s %(process)d %(name)s %(message)s"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "level": LOG_LEVEL, "formatter": "std"},
        "file": {
            "class": "logging.handlers.WatchedFileHandler",
            "filename": WEB_LOG_FILE,
            "level": LOG_LEVEL,
            "formatter": "std",
        },
    },
    "root": {"handlers": ["console", "file"], "level": LOG_LEVEL},
}
