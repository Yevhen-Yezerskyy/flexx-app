# FILE: web/app_panel_admin/views/clients.py  (новое — 2026-02-15)
# PURPOSE: Admin-Panel: Kunden (заглушка) + role-guard.

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from .common import admin_only


@login_required
def clients_list(request: HttpRequest) -> HttpResponse:
    denied = admin_only(request)
    if denied:
        return denied
    return render(request, "app_panel_admin/clients_list.html")
