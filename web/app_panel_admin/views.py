# FILE: web/app_panel_admin/views.py  (новое — 2026-02-13)
# PURPOSE: Index панели Admin + защита от захода чужой ролью.

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.http import HttpRequest, HttpResponse


def _redirect_to_own_panel(role: str) -> HttpResponse:
    if role == "client":
        return redirect("/panel/client/")
    if role == "agent":
        return redirect("/panel/tippgeber/")
    return redirect("/panel/admin/")


@login_required
def index(request: HttpRequest) -> HttpResponse:
    if request.user.role != "admin":
        return _redirect_to_own_panel(request.user.role)
    return render(request, "app_panel_admin/index.html")
