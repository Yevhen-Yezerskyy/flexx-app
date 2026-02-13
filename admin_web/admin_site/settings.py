# FILE: admin_web/admin_site/settings.py  (обновлено — 2026-02-13)
# PURPOSE: Admin settings: импорт “важного” из web/flexx/settings.py (SECRET_KEY/DB/TZ/secure/logging),
#          а тут только отличия: admin apps, cookies, hosts, язык, STATIC_ROOT, DEBUG=False, без AUTH_USER_MODEL.

from __future__ import annotations

import sys
from copy import deepcopy
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Даем админ-проекту возможность импортировать web-проект (/app/web) как модуль "flexx"
WEB_DIR = Path("/app/web")
if str(WEB_DIR) not in sys.path:
    sys.path.insert(0, str(WEB_DIR))

# --- IMPORT COMMON IMPORTANT SETTINGS FROM WEB ---
from flexx.settings import (  # noqa: E402
    SECRET_KEY,
    DATABASES,
    TIME_ZONE,
    USE_TZ,
    SECURE_PROXY_SSL_HEADER,
    USE_X_FORWARDED_HOST,
    CSRF_COOKIE_SECURE,
    SESSION_COOKIE_SECURE,
    LOGGING as WEB_LOGGING,
)

DEBUG = False

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
    "django.contrib.auth",  # стандартный auth.User (таблица auth_user)
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

# NOTE: AUTH_USER_MODEL НЕ задаём — остаётся дефолтный auth.User.

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en"
USE_I18N = True

STATIC_URL = "/static/"
STATIC_ROOT = "/app/admin_static"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- LOGGING: clone web-logging, but write to /app/logs/admin.log ---
LOGGING = deepcopy(WEB_LOGGING)
if "file" in LOGGING.get("handlers", {}):
    LOGGING["handlers"]["file"]["filename"] = "/app/logs/admin.log"
