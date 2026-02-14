# FILE: web/app_panel_admin/views/common.py  (новое — 2026-02-14)
# PURPOSE: Общие хелперы для admin-panel views: role-guard + redirect.

from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect


def redirect_to_own_panel(role: str) -> HttpResponse:
    if role == "client":
        return redirect("/panel/client/")
    if role == "agent":
        return redirect("/panel/tippgeber/")
    return redirect("/panel/admin/")


def admin_only(request: HttpRequest) -> HttpResponse | None:
    if request.user.role != "admin":
        return redirect_to_own_panel(request.user.role)
    return None
