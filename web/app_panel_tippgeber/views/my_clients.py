# FILE: web/app_panel_tippgeber/views/my_clients.py  (обновлено — 2026-03-04)
# PURPOSE: "Meine Kunden": список клиентов текущего Tippgeber.

from __future__ import annotations

from babel.numbers import format_decimal
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from app_users.models import TippgeberClient
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

    links = list(
        TippgeberClient.objects.filter(tippgeber=request.user, client__isnull=False)
        .select_related("client")
        .order_by("-id")
    )
    rows = []
    for link in links:
        if not link.client:
            continue
        rows.append(
            {
                "client": link.client,
                "link": link,
                "expected_investment_amount_display": _format_decimal_de(link.expected_investment_amount, "#,##0.00"),
            }
        )

    return render(request, "app_panel_tippgeber/my_clients.html", {"rows": rows})
