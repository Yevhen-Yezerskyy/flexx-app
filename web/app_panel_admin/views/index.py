# FILE: web/app_panel_admin/views/index.py  (новое — 2026-02-14)
# PURPOSE: Главная страница панели Admin + role-guard.

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from .common import admin_only


@login_required
def index(request: HttpRequest) -> HttpResponse:
    denied = admin_only(request)
    if denied:
        return denied
    return render(request, "app_panel_admin/index.html")
