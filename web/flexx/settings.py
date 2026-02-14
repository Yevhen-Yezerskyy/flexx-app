# FILE: web/flexx/settings.py  (обновлено — 2026-02-13)
# PURPOSE: Web settings: хардкод SECRET_KEY/DB/hosts/logging; единственный env — DJANGO_DEBUG для dev.

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


# ---- POLICY: NO ENVS (except DJANGO_DEBUG) ----

SECRET_KEY = "django-insecure-9m9y9z@%1a6v3q+u7c#r2xw!k8h0$e4p^t1b-5s*o(2n)j6l"
DEBUG = _env_bool("DJANGO_DEBUG", default=False)  # единственный env

ALLOWED_HOSTS = [
    "vertrag.flexxlager.de",
    "dev-vertrag.flexxlager.de",
]

CSRF_TRUSTED_ORIGINS = [
    "https://vertrag.flexxlager.de",
    "https://dev-vertrag.flexxlager.de",
    "http://vertrag.flexxlager.de",
    "http://dev-vertrag.flexxlager.de",
]

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True

INSTALLED_APPS = [
    "flexx",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "app_users",
    "app_panel_client",
    "app_panel_admin",
    "app_panel_tippgeber",
]

AUTH_USER_MODEL = "app_users.FlexxUser"

LOGIN_URL = "/"

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
        "NAME": "flexx",
        "USER": "flexx",
        "PASSWORD": "flexx_passwd",
        "HOST": "postgres",
        "PORT": "5432",
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

# ---------------- LOGGING (hard-coded) ----------------

LOG_DIR = Path("/app/logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)

LOG_LEVEL = "INFO"
WEB_LOG_FILE = str(LOG_DIR / "web.log")

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
