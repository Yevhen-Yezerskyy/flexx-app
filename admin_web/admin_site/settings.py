# FILE: admin_web/admin_site/settings.py  (обновлено — 2026-02-13)
# PURPOSE: Admin-web работает на СТАНДАРТНОЙ Django авторизации (auth.User, таблица auth_user),
#          использует ту же БД, но НЕ использует app_users.FlexxUser как AUTH_USER_MODEL.
#          Добавлены app_panel_* в INSTALLED_APPS + разведены имена cookie, чтобы сессии web/admin не мешались.

from __future__ import annotations

import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Даем админ-проекту возможность импортировать приложения из /app/web (одна кодовая база в контейнере)
WEB_DIR = Path("/app/web")
if str(WEB_DIR) not in sys.path:
    sys.path.insert(0, str(WEB_DIR))

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-only-change-me")
DEBUG = os.getenv("DJANGO_DEBUG", "1") == "1"

ALLOWED_HOSTS = [
    "admin-vertrag.flexxlager.de",
    "admin-vertrag.flexxlager.de.",
]

CSRF_TRUSTED_ORIGINS = [
    "https://admin-vertrag.flexxlager.de",
]

# Важно: отдельные имена cookie, чтобы логины web/admin не пересекались.
SESSION_COOKIE_NAME = "flexx_admin_sessionid"
CSRF_COOKIE_NAME = "flexx_admin_csrftoken"

ROOT_URLCONF = "admin_site.urls"
WSGI_APPLICATION = "admin_site.wsgi.application"

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",  # стандартный auth.User
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "app_users",
    "app_panel_client",
    "app_panel_admin",
    "app_panel_tippgeber",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

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
    },
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("POSTGRES_DB", "flexx"),
        "USER": os.getenv("POSTGRES_USER", "flexx"),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD", "flexx_passwd"),
        "HOST": os.getenv("POSTGRES_HOST", "postgres"),
        "PORT": os.getenv("POSTGRES_PORT", "5432"),
        "CONN_MAX_AGE": int(os.getenv("POSTGRES_CONN_MAX_AGE", "60")),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en"
TIME_ZONE = "Europe/Berlin"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = "/app/admin_static"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ВАЖНО: AUTH_USER_MODEL НЕ задаём — остаётся стандартный auth.User (auth_user).
# AUTH_USER_MODEL = "auth.User"  # не нужно, это дефолт

# ---------------- LOGGING ----------------

LOG_DIR = Path(os.getenv("FLEXX_LOG_DIR", "/app/logs"))
LOG_LEVEL = os.getenv("FLEXX_LOG_LEVEL", "INFO").upper()

try:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
except Exception:
    pass

ADMIN_LOG_FILE = str(LOG_DIR / os.getenv("FLEXX_ADMIN_LOG_FILE", "admin.log"))

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "std": {"format": "%(asctime)s %(levelname)s %(process)d %(name)s %(message)s"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "level": LOG_LEVEL,
            "formatter": "std",
        },
        "file": {
            "class": "logging.handlers.WatchedFileHandler",
            "filename": ADMIN_LOG_FILE,
            "level": LOG_LEVEL,
            "formatter": "std",
        },
    },
    "root": {
        "handlers": ["console", "file"],
        "level": LOG_LEVEL,
    },
}
