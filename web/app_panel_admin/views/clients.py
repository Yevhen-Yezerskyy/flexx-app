# FILE: web/app_panel_admin/views/clients.py  (обновлено — 2026-02-15)
# PURPOSE: Admin-Panel Kunden: toggle актив с confirm+email при активации; добавлен delete (чистит TippgeberClient по client).

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render

from app_panel_admin.forms import AdminClientForm
from app_users.models import FlexxUser, TippgeberClient
from flexx.emailer import send_client_activated_email

from .common import admin_only


@login_required
def clients_list(request: HttpRequest) -> HttpResponse:
    denied = admin_only(request)
    if denied:
        return denied

    clients = FlexxUser.objects.filter(role=FlexxUser.Role.CLIENT).order_by("email")
    links = TippgeberClient.objects.filter(client__in=clients).select_related("client", "tippgeber").all()
    tip_by_client_id = {l.client_id: l.tippgeber for l in links if l.client_id}

    rows = [{"u": c, "tippgeber": tip_by_client_id.get(c.id)} for c in clients]
    return render(request, "app_panel_admin/clients_list.html", {"rows": rows})


@login_required
def clients_create(request: HttpRequest) -> HttpResponse:
    denied = admin_only(request)
    if denied:
        return denied

    if request.method == "POST":
        form = AdminClientForm(request.POST)
        if form.is_valid():
            obj: FlexxUser = form.save(commit=False)
            obj.role = FlexxUser.Role.CLIENT
            if not obj.pk:
                obj.set_unusable_password()
            obj.save()

            _save_tippgeber_link(client=obj, tippgeber_id=form.cleaned_data.get("tippgeber_id"))
            return redirect("panel_admin_clients")
    else:
        form = AdminClientForm(initial={"is_active": True})

    return render(request, "app_panel_admin/clients_form.html", {"form": form, "mode": "create"})


@login_required
def clients_edit(request: HttpRequest, user_id: int) -> HttpResponse:
    denied = admin_only(request)
    if denied:
        return denied

    user = get_object_or_404(FlexxUser, id=user_id, role=FlexxUser.Role.CLIENT)

    if request.method == "POST":
        form = AdminClientForm(request.POST, instance=user)
        if form.is_valid():
            obj: FlexxUser = form.save(commit=False)
            obj.role = FlexxUser.Role.CLIENT
            obj.save()

            _save_tippgeber_link(client=obj, tippgeber_id=form.cleaned_data.get("tippgeber_id"))
            return redirect("panel_admin_clients")
    else:
        form = AdminClientForm(instance=user)

    return render(request, "app_panel_admin/clients_form.html", {"form": form, "mode": "edit", "user": user})


@login_required
def clients_toggle_active(request: HttpRequest, user_id: int) -> HttpResponse:
    denied = admin_only(request)
    if denied:
        return denied

    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    user = get_object_or_404(FlexxUser, id=user_id, role=FlexxUser.Role.CLIENT)
    was_active = bool(user.is_active)
    user.is_active = not was_active
    user.save(update_fields=["is_active"])

    if (not was_active) and user.is_active and request.POST.get("notify") == "1":
        send_client_activated_email(
            to_email=user.email,
            first_name=user.first_name or "",
            last_name=user.last_name or "",
        )

    return redirect("panel_admin_clients")


@login_required
def clients_delete(request: HttpRequest, user_id: int) -> HttpResponse:
    denied = admin_only(request)
    if denied:
        return denied

    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    user = get_object_or_404(FlexxUser, id=user_id, role=FlexxUser.Role.CLIENT)
    TippgeberClient.objects.filter(client=user).delete()
    user.delete()
    return redirect("panel_admin_clients")


def _save_tippgeber_link(*, client: FlexxUser, tippgeber_id: str | None) -> None:
    v = (tippgeber_id or "").strip()
    if not v:
        TippgeberClient.objects.filter(client=client).delete()
        return

    try:
        tid = int(v)
    except Exception:
        return

    tipp = FlexxUser.objects.filter(id=tid, role=FlexxUser.Role.AGENT).first()
    if not tipp:
        TippgeberClient.objects.filter(client=client).delete()
        return

    link = TippgeberClient.objects.filter(client=client).first()
    if not link:
        TippgeberClient.objects.create(client=client, tippgeber=tipp)
        return

    if link.tippgeber_id != tipp.id:
        link.tippgeber = tipp
        link.save(update_fields=["tippgeber"])
