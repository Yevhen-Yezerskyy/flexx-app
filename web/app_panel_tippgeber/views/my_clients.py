# FILE: web/app_panel_tippgeber/views/my_clients.py  (новое — 2026-02-14)
# PURPOSE: Страница "Meine Kunden" панели Tippgeber.

from __future__ import annotations
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from .common import agent_only


@login_required
def my_clients(request: HttpRequest) -> HttpResponse:
    denied = agent_only(request)
    if denied:
        return denied
    return render(request, "app_panel_tippgeber/my_clients.html")
