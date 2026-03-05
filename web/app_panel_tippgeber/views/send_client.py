# FILE: web/app_panel_tippgeber/views/send_client.py  (обновлено — 2026-02-15)
# PURPOSE: Tippgeber send-client flow: форма (tipp+client+consents) → статус (created/exists). При notify_conflict письмо в админку и редирект на "Meine Kunden". Статус показывает данные из формы (cleaned_data), не из БД.

from __future__ import annotations

from babel.numbers import format_decimal
from django.contrib.auth.decorators import login_required
from django.db import transaction
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


STATUS_SESSION_KEY = "panel_tippgeber_send_client_status"


def _format_decimal_de(value, fmt: str) -> str:
    try:
        return format_decimal(value, format=fmt, locale="de_DE")
    except Exception:
        return str(value or "")


def _save_status_state(request: HttpRequest, state: dict) -> None:
    request.session[STATUS_SESSION_KEY] = state
    request.session.modified = True


def _notify_tippgeber_added_interessent(
    *,
    request: HttpRequest,
    client: FlexxUser,
    expected_investment_amount: float,
) -> None:
    try:
        send_tippgeber_added_interessent_email(
            tippgeber_email=getattr(request.user, "email", ""),
            tippgeber_first_name=getattr(request.user, "first_name", ""),
            tippgeber_last_name=getattr(request.user, "last_name", ""),
            client_email=client.email or "",
            client_first_name=client.first_name or "",
            client_last_name=client.last_name or "",
            expected_investment_amount=_format_decimal_de(expected_investment_amount, "#,##0.00"),
        )
    except Exception:
        pass


def _parse_positive_int(v: str | None) -> int | None:
    try:
        n = int((v or "").strip())
    except Exception:
        return None
    return n if n > 0 else None


def _get_tippgeber_link_by_client_id(request: HttpRequest, client_id: int | None) -> TippgeberClient | None:
    if not client_id:
        return None
    return (
        TippgeberClient.objects.select_related("client")
        .filter(tippgeber=request.user, client_id=client_id)
        .first()
    )


@login_required
def send_client(request: HttpRequest) -> HttpResponse:
    denied = agent_only(request)
    if denied:
        return denied

    today = timezone.localdate()

    editing_client_id = _parse_positive_int(request.GET.get("client_id"))
    editing_link = _get_tippgeber_link_by_client_id(request, editing_client_id)
    editing_client = editing_link.client if editing_link and editing_link.client else None

    tipp_form = TippgeberProfileForm(prefix="tipp", instance=request.user)
    client_initial = {}
    if editing_link:
        client_initial["expected_investment_amount"] = editing_link.expected_investment_amount
    if editing_client:
        client_form = ClientCreateForm(prefix="client", instance=editing_client, initial=client_initial)
    else:
        client_form = ClientCreateForm(prefix="client", initial=client_initial)
    conf_form = ConfirmationsForm(prefix="conf")

    if request.method == "POST":
        action = (request.POST.get("action") or "send").strip()
        editing_client_id = _parse_positive_int(request.POST.get("editing_client_id"))
        editing_link = _get_tippgeber_link_by_client_id(request, editing_client_id)
        editing_client = editing_link.client if editing_link and editing_link.client else None

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
        if editing_client:
            client_form = ClientCreateForm(request.POST, prefix="client", instance=editing_client)
        else:
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
                    "editing_client_id": editing_client_id,
                    "today": today,
                    "state": {"err": "Bitte prüfen Sie die markierten Felder."},
                },
            )

        tipp_form.save()
        cd = client_form.cleaned_data
        expected_investment_amount = float(cd["expected_investment_amount"])
        expected_investment_amount_display = _format_decimal_de(expected_investment_amount, "#,##0.00")
        email = (cd.get("email") or "").strip().lower()
        existing = FlexxUser.objects.filter(email=email).first()

        if existing:
            link = TippgeberClient.objects.filter(client=existing).first()
            client_is_mine = bool(link and link.tippgeber_id == request.user.id)

            if client_is_mine and existing.role == FlexxUser.Role.CLIENT:
                with transaction.atomic():
                    if editing_client and editing_client.id == existing.id:
                        updated_client: FlexxUser = client_form.save(commit=False)
                        updated_client.role = FlexxUser.Role.CLIENT
                        updated_client.is_active = existing.is_active
                        updated_client.save()
                        existing = updated_client
                    if link:
                        link.expected_investment_amount = expected_investment_amount
                        link.save(update_fields=["expected_investment_amount"])
                    else:
                        TippgeberClient.objects.create(
                            tippgeber=request.user,
                            client=existing,
                            expected_investment_amount=expected_investment_amount,
                        )
                _notify_tippgeber_added_interessent(
                    request=request,
                    client=existing,
                    expected_investment_amount=expected_investment_amount,
                )
                mode = "updated" if editing_client else "exists"
            else:
                mode = "exists"

            state = {
                "mode": mode,
                "ok": "",
                "err": "",
                "conflict_notified": False,
                "client_is_mine": client_is_mine,
                "client_email": existing.email if client_is_mine else email,
                "client_first_name": (existing.first_name or "").strip() if client_is_mine else (cd.get("first_name") or "").strip(),
                "client_last_name": (existing.last_name or "").strip() if client_is_mine else (cd.get("last_name") or "").strip(),
                "client_company": (existing.company or "").strip() if client_is_mine else (cd.get("company") or "").strip(),
                "client_street": (existing.street or "").strip() if client_is_mine else (cd.get("street") or "").strip(),
                "client_zip_code": (existing.zip_code or "").strip() if client_is_mine else (cd.get("zip_code") or "").strip(),
                "client_city": (existing.city or "").strip() if client_is_mine else (cd.get("city") or "").strip(),
                "client_phone": (existing.phone or "").strip() if client_is_mine else (cd.get("phone") or "").strip(),
                "client_mobile_phone": (existing.mobile_phone or "").strip() if client_is_mine else (cd.get("mobile_phone") or "").strip(),
                "expected_investment_amount_display": expected_investment_amount_display,
            }
            _save_status_state(request, state)
            return redirect("panel_tippgeber_send_client_status")

        with transaction.atomic():
            new_client: FlexxUser = client_form.save(commit=False)
            new_client.role = FlexxUser.Role.CLIENT
            new_client.is_active = False
            new_client.set_unusable_password()
            new_client.save()

            TippgeberClient.objects.create(
                tippgeber=request.user,
                client=new_client,
                expected_investment_amount=expected_investment_amount,
            )

        _notify_tippgeber_added_interessent(
            request=request,
            client=new_client,
            expected_investment_amount=expected_investment_amount,
        )

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
            "client_street": (cd.get("street") or "").strip(),
            "client_zip_code": (cd.get("zip_code") or "").strip(),
            "client_city": (cd.get("city") or "").strip(),
            "client_phone": (cd.get("phone") or "").strip(),
            "client_mobile_phone": (cd.get("mobile_phone") or "").strip(),
            "expected_investment_amount_display": expected_investment_amount_display,
        }
        _save_status_state(request, state)
        return redirect("panel_tippgeber_send_client_status")

    return render(
        request,
        "app_panel_tippgeber/send_client.html",
        {
            "tipp_form": tipp_form,
            "client_form": client_form,
            "conf_form": conf_form,
            "editing_client_id": editing_client_id,
            "today": today,
            "state": {},
        },
    )


@login_required
def send_client_status(request: HttpRequest) -> HttpResponse:
    denied = agent_only(request)
    if denied:
        return denied

    state = request.session.get(STATUS_SESSION_KEY)
    if not isinstance(state, dict):
        return redirect("panel_tippgeber_send_client")

    return render(
        request,
        "app_panel_tippgeber/client_status.html",
        {
            "today": timezone.localdate(),
            "state": state,
        },
    )
