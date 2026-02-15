# FILE: web/app_panel_tippgeber/views/my_clients.py  (обновлено — 2026-02-15)
# PURPOSE: "Meine Kunden": список клиентов, привязанных к текущему Tippgeber через TippgeberClient.

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from app_users.models import TippgeberClient
from .common import agent_only


@login_required
def my_clients(request: HttpRequest) -> HttpResponse:
    denied = agent_only(request)
    if denied:
        return denied

    links = (
        TippgeberClient.objects.select_related("client")
        .filter(tippgeber=request.user, client__isnull=False)
        .order_by("-created_at")
    )
    clients = [l.client for l in links if l.client]

    return render(request, "app_panel_tippgeber/my_clients.html", {"clients": clients})
