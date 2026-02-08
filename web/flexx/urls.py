# FILE: web/flexx/urls.py  (обновлено — 2026-02-08)
# PURPOSE: Подключить app_users как главную страницу, оставить admin.

from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("app_users.urls")),
]