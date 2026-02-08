# FILE: web/app_users/views.py  (новое — 2026-02-08)
# PURPOSE: Временный view: просто показать страницу с формой логина (без логики).

from django.shortcuts import render


def home(request):
    return render(request, "app_users/login.html")
