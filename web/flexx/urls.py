# FILE: web/flexx/urls.py  (обновлено — 2026-02-12)
# PURPOSE: Подключить app_users как главную страницу; встроенную Django-админку в web выключить.

from django.urls import path, include

urlpatterns = [
    path("", include("app_users.urls")),
]
