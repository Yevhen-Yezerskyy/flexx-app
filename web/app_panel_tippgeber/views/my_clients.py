# FILE: web/app_panel_tippgeber/views/my_clients.py  (обновлено — 2026-02-15)
# PURPOSE: "Meine Kunden": список клиентов, привязанных к текущему Tippgeber через TippgeberClient.

from __future__ import annotations

from babel.numbers import format_decimal
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from app_users.models import TippgeberClient
from flexx.models import Contract
from .common import agent_only


def _format_decimal_de(value, fmt: str) -> str:
    try:
        return format_decimal(value, format=fmt, locale="de_DE")
    except Exception:
        return str(value or "")


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
    client_ids = [c.id for c in clients if c and c.id]
    contracts = (
        Contract.objects.filter(client_id__in=client_ids)
        .order_by("-contract_date", "-id")
        .all()
    )
    latest_contract_by_client_id: dict[int, Contract] = {}
    for c in contracts:
        if c.client_id not in latest_contract_by_client_id:
            latest_contract_by_client_id[c.client_id] = c

    rows = []
    for client in clients:
        c = latest_contract_by_client_id.get(client.id)
        rows.append(
            {
                "client": client,
                "contract": c,
                "contract_total_display": _format_decimal_de(c.nominal_amount_plus_percent, "#,##0.00") if c and c.nominal_amount_plus_percent is not None else "",
            }
        )

    return render(request, "app_panel_tippgeber/my_clients.html", {"rows": rows})
