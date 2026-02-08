# FILE: web/app_users/urls.py  (новое — 2026-02-08)
# PURPOSE: Временный роут: главная страница → home().

from django.urls import path
from .views import home

urlpatterns = [
    path("", home, name="home"),
]
