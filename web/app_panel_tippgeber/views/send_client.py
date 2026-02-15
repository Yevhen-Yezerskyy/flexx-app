# FILE: web/app_panel_tippgeber/views/send_client.py  (обновлено — 2026-02-15)
# PURPOSE: Исправление пустых полей после submit: формы Tippgeber/Client/Confirmations теперь с prefix (tipp/client/conf), чтобы POST-ключи не конфликтовали.

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.utils import timezone

from app_users.models import FlexxUser, TippgeberClient
from flexx.emailer import send_tippgeber_added_interessent_email, send_tippgeber_link_conflict_email
from .common import agent_only
from ..forms import TippgeberProfileForm, ClientCreateForm, ConfirmationsForm


@login_required
def send_client(request: HttpRequest) -> HttpResponse:
    denied = agent_only(request)
    if denied:
        return denied

    today = timezone.localdate()

    state = {
        "ok": "",
        "err": "",
        "client_is_mine": False,
        "client_is_other": False,
        "conflict_notified": False,
        "existing_client_email": "",
        "existing_client_first_name": "",
        "existing_client_last_name": "",
    }

    tipp_form = TippgeberProfileForm(prefix="tipp", instance=request.user)
    client_form = ClientCreateForm(prefix="client")
    conf_form = ConfirmationsForm(prefix="conf")

    if request.method == "POST":
        action = (request.POST.get("action") or "send").strip()

        tipp_form = TippgeberProfileForm(request.POST, prefix="tipp", instance=request.user)
        client_form = ClientCreateForm(request.POST, prefix="client")
        conf_form = ConfirmationsForm(request.POST, prefix="conf")

        if action == "notify_conflict":
            ex_email = (request.POST.get("existing_client_email") or "").strip().lower()
            ex_fn = (request.POST.get("existing_client_first_name") or "").strip()
            ex_ln = (request.POST.get("existing_client_last_name") or "").strip()

            send_tippgeber_link_conflict_email(
                tippgeber_email=getattr(request.user, "email", ""),
                tippgeber_first_name=getattr(request.user, "first_name", ""),
                tippgeber_last_name=getattr(request.user, "last_name", ""),
                client_email=ex_email,
                client_first_name=ex_fn,
                client_last_name=ex_ln,
            )

            state["ok"] = "Nachricht wurde gesendet."
            state["client_is_other"] = True
            state["conflict_notified"] = True
            state["existing_client_email"] = ex_email
            state["existing_client_first_name"] = ex_fn
            state["existing_client_last_name"] = ex_ln

            return render(
                request,
                "app_panel_tippgeber/send_client.html",
                {"tipp_form": tipp_form, "client_form": client_form, "conf_form": conf_form, "today": today, "state": state},
            )

        valid = tipp_form.is_valid() and client_form.is_valid() and conf_form.is_valid()
        if not valid:
            state["err"] = "Bitte prüfen Sie die markierten Felder."
        else:
            tipp_form.save()

            email = (client_form.cleaned_data.get("email") or "").strip().lower()
            existing = FlexxUser.objects.filter(email=email).first()

            if existing:
                state["existing_client_email"] = existing.email
                state["existing_client_first_name"] = existing.first_name or ""
                state["existing_client_last_name"] = existing.last_name or ""

                link = TippgeberClient.objects.filter(client=existing).first()
                if link and link.tippgeber_id == request.user.id:
                    state["client_is_mine"] = True
                    state["ok"] = "Dieser Kunde ist bereits bei Ihnen registriert."
                else:
                    state["client_is_other"] = True
                    state["err"] = "Dieser Kunde ist bereits bei uns registriert."
            else:
                new_client: FlexxUser = client_form.save(commit=False)
                new_client.role = FlexxUser.Role.CLIENT
                new_client.is_active = False
                new_client.set_unusable_password()
                new_client.save()

                TippgeberClient.objects.create(tippgeber=request.user, client=new_client)

                send_tippgeber_added_interessent_email(
                    tippgeber_email=getattr(request.user, "email", ""),
                    tippgeber_first_name=getattr(request.user, "first_name", ""),
                    tippgeber_last_name=getattr(request.user, "last_name", ""),
                    client_email=new_client.email,
                    client_first_name=new_client.first_name or "",
                    client_last_name=new_client.last_name or "",
                )

                state["ok"] = "Der Interessent wurde übermittelt."
                client_form = ClientCreateForm(prefix="client")
                conf_form = ConfirmationsForm(prefix="conf")

    return render(
        request,
        "app_panel_tippgeber/send_client.html",
        {"tipp_form": tipp_form, "client_form": client_form, "conf_form": conf_form, "today": today, "state": state},
    )
