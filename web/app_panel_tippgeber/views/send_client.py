# FILE: web/app_panel_tippgeber/views/send_client.py  (обновлено — 2026-02-15)
# PURPOSE: Tippgeber send-client flow: форма (tipp+client+consents) → статус (created/exists). При notify_conflict письмо в админку и редирект на "Meine Kunden". Статус показывает данные из формы (cleaned_data), не из БД.

from __future__ import annotations

from datetime import date

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone

from app_users.models import FlexxUser, TippgeberClient
from flexx.emailer import (
    send_tippgeber_added_interessent_email,
    send_tippgeber_link_conflict_email,
)
from .common import agent_only
from ..forms import ClientCreateForm, ConfirmationsForm, TippgeberProfileForm


def _parse_iso_date(v: str) -> date | None:
    v = (v or "").strip()
    if not v:
        return None
    try:
        return date.fromisoformat(v)
    except Exception:
        return None


@login_required
def send_client(request: HttpRequest) -> HttpResponse:
    denied = agent_only(request)
    if denied:
        return denied

    today = timezone.localdate()

    tipp_form = TippgeberProfileForm(prefix="tipp", instance=request.user)
    client_form = ClientCreateForm(prefix="client")
    conf_form = ConfirmationsForm(prefix="conf")

    if request.method == "POST":
        action = (request.POST.get("action") or "send").strip()

        # ---- conflict notify ----
        if action == "notify_conflict":
            ex_email = (request.POST.get("client_email") or "").strip().lower()

            try:
                send_tippgeber_link_conflict_email(
                    tippgeber_email=getattr(request.user, "email", ""),
                    tippgeber_first_name=getattr(request.user, "first_name", ""),
                    tippgeber_last_name=getattr(request.user, "last_name", ""),
                    client_email=ex_email,
                    client_first_name=(request.POST.get("client_first_name") or "").strip(),
                    client_last_name=(request.POST.get("client_last_name") or "").strip(),
                )
            except Exception:
                pass

            return redirect("panel_tippgeber_my_clients")

        # ---- main submit ----
        tipp_form = TippgeberProfileForm(request.POST, prefix="tipp", instance=request.user)
        client_form = ClientCreateForm(request.POST, prefix="client")
        conf_form = ConfirmationsForm(request.POST, prefix="conf")

        if not (tipp_form.is_valid() and client_form.is_valid() and conf_form.is_valid()):
            return render(
                request,
                "app_panel_tippgeber/send_client.html",
                {
                    "tipp_form": tipp_form,
                    "client_form": client_form,
                    "conf_form": conf_form,
                    "today": today,
                    "state": {"err": "Bitte prüfen Sie die markierten Felder."},
                },
            )

        # сохраняем данные типпбергера (как было)
        tipp_form.save()

        cd = client_form.cleaned_data
        email = (cd.get("email") or "").strip().lower()

        existing = FlexxUser.objects.filter(email=email).first()
        if existing:
            link = TippgeberClient.objects.filter(client=existing).first()
            client_is_mine = bool(link and link.tippgeber_id == request.user.id)

            state = {
                "mode": "exists",
                "ok": "",
                "err": "",
                "conflict_notified": False,
                "client_is_mine": client_is_mine,
                # показываем именно то, что ввели в форме
                "client_email": email,
                "client_first_name": (cd.get("first_name") or "").strip(),
                "client_last_name": (cd.get("last_name") or "").strip(),
                "client_company": (cd.get("company") or "").strip(),
                "client_birth_date": cd.get("birth_date"),
                "client_street": (cd.get("street") or "").strip(),
                "client_zip_code": (cd.get("zip_code") or "").strip(),
                "client_city": (cd.get("city") or "").strip(),
                "client_phone": (cd.get("phone") or "").strip(),
                "client_mobile_phone": (cd.get("mobile_phone") or "").strip(),
            }
            return render(request, "app_panel_tippgeber/client_status.html", {"today": today, "state": state})

        new_client: FlexxUser = client_form.save(commit=False)
        new_client.role = FlexxUser.Role.CLIENT
        new_client.is_active = False
        new_client.set_unusable_password()
        new_client.save()

        TippgeberClient.objects.create(tippgeber=request.user, client=new_client)

        try:
            send_tippgeber_added_interessent_email(
                tippgeber_email=getattr(request.user, "email", ""),
                tippgeber_first_name=getattr(request.user, "first_name", ""),
                tippgeber_last_name=getattr(request.user, "last_name", ""),
                client_email=new_client.email,
                client_first_name=new_client.first_name or "",
                client_last_name=new_client.last_name or "",
            )
        except Exception:
            pass

        state = {
            "mode": "created",
            "ok": "",
            "err": "",
            "conflict_notified": False,
            "client_is_mine": False,
            "client_email": email,
            "client_first_name": (cd.get("first_name") or "").strip(),
            "client_last_name": (cd.get("last_name") or "").strip(),
            "client_company": (cd.get("company") or "").strip(),
            "client_birth_date": cd.get("birth_date"),
            "client_street": (cd.get("street") or "").strip(),
            "client_zip_code": (cd.get("zip_code") or "").strip(),
            "client_city": (cd.get("city") or "").strip(),
            "client_phone": (cd.get("phone") or "").strip(),
            "client_mobile_phone": (cd.get("mobile_phone") or "").strip(),
        }
        return render(request, "app_panel_tippgeber/client_status.html", {"today": today, "state": state})

    return render(
        request,
        "app_panel_tippgeber/send_client.html",
        {"tipp_form": tipp_form, "client_form": client_form, "conf_form": conf_form, "today": today, "state": {}},
    )
