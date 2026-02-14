# FILE: web/app_panel_admin/views/tippgeber.py  (новое — 2026-02-14)
# PURPOSE: Admin-Panel: список Tippgeber (role=agent) + activate/deactivate; при активации отправляем письмо.

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from app_users.models import FlexxUser
from flexx.emailer import send_account_activated_email

from .common import admin_only


@login_required
def tippgeber_list(request: HttpRequest) -> HttpResponse:
    denied = admin_only(request)
    if denied:
        return denied

    tippgebers = FlexxUser.objects.filter(role=FlexxUser.Role.AGENT).order_by("email")
    return render(request, "app_panel_admin/tippgeber_list.html", {"tippgebers": tippgebers})


@login_required
def tippgeber_activate(request: HttpRequest, user_id: int) -> HttpResponse:
    denied = admin_only(request)
    if denied:
        return denied

    if request.method != "POST":
        return redirect("panel_admin_tippgeber_list")

    user = get_object_or_404(FlexxUser, id=user_id, role=FlexxUser.Role.AGENT)
    user.is_active = True
    user.save(update_fields=["is_active"])

    send_account_activated_email(
        to_email=user.email,
        first_name=user.first_name or "",
        last_name=user.last_name or "",
    )

    return redirect("panel_admin_tippgeber_list")


@login_required
def tippgeber_deactivate(request: HttpRequest, user_id: int) -> HttpResponse:
    denied = admin_only(request)
    if denied:
        return denied

    if request.method != "POST":
        return redirect("panel_admin_tippgeber_list")

    user = get_object_or_404(FlexxUser, id=user_id, role=FlexxUser.Role.AGENT)
    user.is_active = False
    user.save(update_fields=["is_active"])

    return redirect("panel_admin_tippgeber_list")
