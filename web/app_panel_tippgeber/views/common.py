# FILE: web/app_panel_tippgeber/views/common.py  (новое — 2026-02-14)
# PURPOSE: Проверка роли agent и редирект в свою панель.

from __future__ import annotations
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect


def redirect_to_own_panel(role: str) -> HttpResponse:
    if role == "admin":
        return redirect("/panel/admin/")
    if role == "client":
        return redirect("/panel/client/")
    return redirect("/panel/tippgeber/")


def agent_only(request: HttpRequest) -> HttpResponse | None:
    if getattr(request.user, "role", None) != "agent":
        return redirect_to_own_panel(getattr(request.user, "role", ""))
    return None
