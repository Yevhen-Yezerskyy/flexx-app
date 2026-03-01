# FILE: web/app_panel_tippgeber/views/my_clients.py  (обновлено — 2026-02-27)
# PURPOSE: "Meine Kunden/Verträge": список договоров текущего Tippgeber (одна строка = один Vertrag).

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from app_users.models import TippgeberClient
from flexx.models import Contract
from .common import agent_only


@login_required
def my_clients(request: HttpRequest) -> HttpResponse:
    denied = agent_only(request)
    if denied:
        return denied

    client_ids = list(
        TippgeberClient.objects.filter(tippgeber=request.user, client__isnull=False)
        .values_list("client_id", flat=True)
    )

    rows = []
    if client_ids:
        contracts = (
            Contract.objects.select_related("client", "issue")
            .filter(client_id__in=client_ids)
            .order_by("-id")
            .all()
        )
        rows = [{"client": c.client, "contract": c} for c in contracts if c.client]

    return render(request, "app_panel_tippgeber/my_clients.html", {"rows": rows})
