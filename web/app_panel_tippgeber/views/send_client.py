# FILE: web/app_panel_tippgeber/views/send_client.py  (новое — 2026-02-14)
# PURPOSE: Главная страница панели Tippgeber = "Kunden senden".

from __future__ import annotations
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from .common import agent_only


@login_required
def send_client(request: HttpRequest) -> HttpResponse:
    denied = agent_only(request)
    if denied:
        return denied
    return render(request, "app_panel_tippgeber/send_client.html")
