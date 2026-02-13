# FILE: web/app_panel_client/views.py  (новое — 2026-02-13)
# PURPOSE: Index панели Client + защита от захода чужой ролью.

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.http import HttpRequest, HttpResponse


def _redirect_to_own_panel(role: str) -> HttpResponse:
    if role == "admin":
        return redirect("/panel/admin/")
    if role == "agent":
        return redirect("/panel/tippgeber/")
    return redirect("/panel/client/")


@login_required
def index(request: HttpRequest) -> HttpResponse:
    if request.user.role != "client":
        return _redirect_to_own_panel(request.user.role)
    return render(request, "app_panel_client/index.html")
