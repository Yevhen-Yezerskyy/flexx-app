# FILE: web/app_panel_admin/views/tippgeber.py  (обновлено — 2026-02-15)
# PURPOSE: Admin-Panel: Tippgeber list (с его Kunden), edit/delete, POST toggle aktiv/inaktiv с confirm-уведомлением по email при активации.

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render

from app_panel_admin.forms import AdminTippgeberForm
from app_users.models import FlexxUser, TippgeberClient
from flexx.emailer import send_tippgeber_activated_email, send_tippgeber_deleted_email

from .common import admin_only, build_set_password_url


@login_required
def tippgeber_list(request: HttpRequest) -> HttpResponse:
    denied = admin_only(request)
    if denied:
        return denied

    tips = FlexxUser.objects.filter(role=FlexxUser.Role.AGENT).order_by("email")
    links = (
        TippgeberClient.objects.filter(tippgeber__in=tips)
        .select_related("tippgeber", "client")
        .order_by("client__email")
    )

    clients_by_tip_id: dict[int, list[FlexxUser]] = {}
    for l in links:
        if not l.tippgeber_id or not l.client_id:
            continue
        clients_by_tip_id.setdefault(l.tippgeber_id, []).append(l.client)

    rows = []
    for t in tips:
        rows.append({"u": t, "clients": clients_by_tip_id.get(t.id, [])})

    return render(request, "app_panel_admin/tippgeber_list.html", {"rows": rows})


@login_required
def tippgeber_edit(request: HttpRequest, user_id: int) -> HttpResponse:
    denied = admin_only(request)
    if denied:
        return denied

    user = get_object_or_404(FlexxUser, id=user_id, role=FlexxUser.Role.AGENT)

    if request.method == "POST":
        form = AdminTippgeberForm(request.POST, instance=user)
        if form.is_valid():
            obj: FlexxUser = form.save(commit=False)
            obj.role = FlexxUser.Role.AGENT
            obj.save()
            return redirect("panel_admin_tippgeber_list")
    else:
        form = AdminTippgeberForm(instance=user)

    return render(request, "app_panel_admin/tippgeber_form.html", {"form": form, "user": user})


@login_required
def tippgeber_toggle_active(request: HttpRequest, user_id: int) -> HttpResponse:
    denied = admin_only(request)
    if denied:
        return denied

    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    user = get_object_or_404(FlexxUser, id=user_id, role=FlexxUser.Role.AGENT)
    was_active = bool(user.is_active)
    user.is_active = not was_active
    user.save(update_fields=["is_active"])

    if (not was_active) and user.is_active and request.POST.get("notify") == "1":
        set_password_url = ""
        if not user.has_usable_password():
            set_password_url = build_set_password_url(request, user)
        send_tippgeber_activated_email(
            to_email=user.email,
            first_name=user.first_name or "",
            last_name=user.last_name or "",
            set_password_url=set_password_url,
        )

    return redirect("panel_admin_tippgeber_list")


@login_required
def tippgeber_delete(request: HttpRequest, user_id: int) -> HttpResponse:
    denied = admin_only(request)
    if denied:
        return denied

    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    user = get_object_or_404(FlexxUser, id=user_id, role=FlexxUser.Role.AGENT)
    if request.POST.get("notify") == "1":
        send_tippgeber_deleted_email(
            to_email=user.email,
            first_name=user.first_name or "",
            last_name=user.last_name or "",
        )
    TippgeberClient.objects.filter(tippgeber=user).delete()
    user.delete()
    return redirect("panel_admin_tippgeber_list")
