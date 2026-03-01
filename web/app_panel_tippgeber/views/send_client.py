# FILE: web/app_panel_tippgeber/views/send_client.py  (обновлено — 2026-02-15)
# PURPOSE: Tippgeber send-client flow: форма (tipp+client+consents) → статус (created/exists). При notify_conflict письмо в админку и редирект на "Meine Kunden". Статус показывает данные из формы (cleaned_data), не из БД.

from __future__ import annotations

from datetime import date

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
from flexx.models import BondIssue, Contract
from .common import agent_only
from ..forms import ClientCreateForm, ConfirmationsForm, TippgeberProfileForm


STATUS_SESSION_KEY = "panel_tippgeber_send_client_status"


def _parse_iso_date(v: str) -> date | None:
    v = (v or "").strip()
    if not v:
        return None
    try:
        return date.fromisoformat(v)
    except Exception:
        return None


def _format_decimal_de(value, fmt: str) -> str:
    try:
        return format_decimal(value, format=fmt, locale="de_DE")
    except Exception:
        return str(value or "")


def _load_active_issues():
    issues = (
        BondIssue.objects.filter(active=True)
        .all()
        .order_by("-issue_date", "-id")
    )
    for issue in issues:
        issue.bond_price_display = _format_decimal_de(issue.bond_price, "#,##0.00")
        issue.issue_volume_display = _format_decimal_de(issue.issue_volume, "#,##0.00")
        issue.minimal_bonds_quantity_display = _format_decimal_de(issue.minimal_bonds_quantity, "#,##0")
    return list(issues)


def _save_status_state(request: HttpRequest, state: dict) -> None:
    request.session[STATUS_SESSION_KEY] = state
    request.session.modified = True


def _notify_tippgeber_added_interessent(
    *,
    request: HttpRequest,
    client: FlexxUser,
    issue: BondIssue,
) -> None:
    try:
        send_tippgeber_added_interessent_email(
            tippgeber_email=getattr(request.user, "email", ""),
            tippgeber_first_name=getattr(request.user, "first_name", ""),
            tippgeber_last_name=getattr(request.user, "last_name", ""),
            client_email=client.email or "",
            client_first_name=client.first_name or "",
            client_last_name=client.last_name or "",
            issue_date=issue.issue_date,
            issue_title=issue.title,
        )
    except Exception:
        pass


def _parse_positive_int(v: str | None) -> int | None:
    try:
        n = int((v or "").strip())
    except Exception:
        return None
    return n if n > 0 else None


def _get_tippgeber_client_by_id(request: HttpRequest, client_id: int | None) -> FlexxUser | None:
    if not client_id:
        return None
    link = (
        TippgeberClient.objects.select_related("client")
        .filter(tippgeber=request.user, client_id=client_id)
        .first()
    )
    if not link or not link.client:
        return None
    return link.client


@login_required
def send_client(request: HttpRequest) -> HttpResponse:
    denied = agent_only(request)
    if denied:
        return denied

    today = timezone.localdate()

    editing_client_id = _parse_positive_int(request.GET.get("client_id"))
    editing_client = _get_tippgeber_client_by_id(request, editing_client_id)

    tipp_form = TippgeberProfileForm(prefix="tipp", instance=request.user)
    if editing_client:
        client_form = ClientCreateForm(prefix="client", instance=editing_client)
    else:
        client_form = ClientCreateForm(prefix="client")
    conf_form = ConfirmationsForm(prefix="conf")
    issues = _load_active_issues()
    selected_issue_id = issues[0].id if issues else None
    issue_error: str | None = None

    if request.method == "POST":
        action = (request.POST.get("action") or "send").strip()
        editing_client_id = _parse_positive_int(request.POST.get("editing_client_id"))
        editing_client = _get_tippgeber_client_by_id(request, editing_client_id)
        issue_id_raw = (request.POST.get("issue_id") or "").strip()
        if issue_id_raw:
            try:
                selected_issue_id = int(issue_id_raw)
            except Exception:
                selected_issue_id = None

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
        posted_client_email = (request.POST.get(client_form.add_prefix("email")) or "").strip().lower()
        existing_by_email = (
            FlexxUser.objects.filter(email=posted_client_email).first()
            if posted_client_email
            else None
        )

        own_existing_client: FlexxUser | None = None
        if editing_client:
            own_existing_client = editing_client
        elif existing_by_email and existing_by_email.role == FlexxUser.Role.CLIENT:
            if TippgeberClient.objects.filter(tippgeber=request.user, client=existing_by_email).exists():
                own_existing_client = existing_by_email

        if not (tipp_form.is_valid() and conf_form.is_valid()):
            return render(
                request,
                "app_panel_tippgeber/send_client.html",
                {
                    "tipp_form": tipp_form,
                    "client_form": client_form,
                    "conf_form": conf_form,
                    "issues": issues,
                    "selected_issue_id": selected_issue_id,
                    "issue_error": issue_error,
                    "editing_client_id": editing_client_id,
                    "today": today,
                    "state": {"err": "Bitte prüfen Sie die markierten Felder."},
                },
            )

        selected_issue = next((it for it in issues if it.id == selected_issue_id), None)
        if selected_issue is None:
            issue_error = "Bitte wählen Sie eine Emission aus."
            return render(
                request,
                "app_panel_tippgeber/send_client.html",
                {
                    "tipp_form": tipp_form,
                    "client_form": client_form,
                    "conf_form": conf_form,
                    "issues": issues,
                    "selected_issue_id": selected_issue_id,
                    "issue_error": issue_error,
                    "editing_client_id": editing_client_id,
                    "today": today,
                    "state": {"err": "Bitte prüfen Sie die markierten Felder."},
                },
            )

        # сохраняем данные типпбергера (как было)
        tipp_form.save()

        if own_existing_client:
            created_contract = Contract.objects.create(
                client=own_existing_client,
                issue=selected_issue,
            )
            _notify_tippgeber_added_interessent(
                request=request,
                client=own_existing_client,
                issue=selected_issue,
            )
            state = {
                "mode": "exists",
                "ok": "",
                "err": "",
                "conflict_notified": False,
                "client_is_mine": True,
                "client_email": own_existing_client.email,
                "client_first_name": (own_existing_client.first_name or "").strip(),
                "client_last_name": (own_existing_client.last_name or "").strip(),
                "client_company": (own_existing_client.company or "").strip(),
                "client_street": (own_existing_client.street or "").strip(),
                "client_zip_code": (own_existing_client.zip_code or "").strip(),
                "client_city": (own_existing_client.city or "").strip(),
                "client_phone": (own_existing_client.phone or "").strip(),
                "client_mobile_phone": (own_existing_client.mobile_phone or "").strip(),
                "contract_created": True,
                "contract_id": created_contract.id,
            }
            _save_status_state(request, state)
            return redirect("panel_tippgeber_send_client_status")

        if not client_form.is_valid():
            return render(
                request,
                "app_panel_tippgeber/send_client.html",
                {
                    "tipp_form": tipp_form,
                    "client_form": client_form,
                    "conf_form": conf_form,
                    "issues": issues,
                    "selected_issue_id": selected_issue_id,
                    "issue_error": issue_error,
                    "editing_client_id": editing_client_id,
                    "today": today,
                    "state": {"err": "Bitte prüfen Sie die markierten Felder."},
                },
            )

        cd = client_form.cleaned_data
        email = (cd.get("email") or "").strip().lower()

        existing = FlexxUser.objects.filter(email=email).first()
        if existing:
            link = TippgeberClient.objects.filter(client=existing).first()
            client_is_mine = bool(link and link.tippgeber_id == request.user.id)
            contract_created = False
            created_contract: Contract | None = None
            if client_is_mine and existing.role == FlexxUser.Role.CLIENT:
                created_contract = Contract.objects.create(
                    client=existing,
                    issue=selected_issue,
                )
                contract_created = True
                _notify_tippgeber_added_interessent(
                    request=request,
                    client=existing,
                    issue=selected_issue,
                )

            state = {
                "mode": "exists",
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
                "contract_created": contract_created,
                "contract_id": created_contract.id if created_contract else None,
            }
            _save_status_state(request, state)
            return redirect("panel_tippgeber_send_client_status")

        with transaction.atomic():
            new_client: FlexxUser = client_form.save(commit=False)
            new_client.role = FlexxUser.Role.CLIENT
            new_client.is_active = False
            new_client.set_unusable_password()
            new_client.save()

            created_contract = Contract.objects.create(
                client=new_client,
                issue=selected_issue,
            )
            TippgeberClient.objects.create(tippgeber=request.user, client=new_client)

        _notify_tippgeber_added_interessent(
            request=request,
            client=new_client,
            issue=selected_issue,
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
            "contract_created": True,
            "contract_id": created_contract.id,
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
            "issues": issues,
            "selected_issue_id": selected_issue_id,
            "issue_error": issue_error,
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

    contract = None
    if state.get("contract_created"):
        contract_id_raw = state.get("contract_id")
        try:
            contract_id = int(contract_id_raw)
        except Exception:
            contract_id = 0
        if contract_id > 0:
            contract = (
                Contract.objects.select_related("client", "issue")
                .filter(id=contract_id)
                .first()
            )
        if contract is None:
            raise RuntimeError(
                "Broken status state: contract_created=True but contract not found for contract_id."
            )

    issue_bond_price_display = ""
    issue_volume_display = ""
    issue_minimal_bonds_quantity_display = ""
    issue_display_title = ""
    if contract and contract.issue_id:
        issue_bond_price_display = _format_decimal_de(contract.issue.bond_price, "#,##0.00")
        issue_volume_display = _format_decimal_de(contract.issue.issue_volume, "#,##0.00")
        issue_minimal_bonds_quantity_display = _format_decimal_de(
            contract.issue.minimal_bonds_quantity,
            "#,##0",
        )
        issue_display_title = f"{contract.issue.issue_date:%d.%m.%Y}: {contract.issue.title}"

    return render(
        request,
        "app_panel_tippgeber/client_status.html",
        {
            "today": timezone.localdate(),
            "state": state,
            "contract": contract,
            "issue_bond_price_display": issue_bond_price_display,
            "issue_volume_display": issue_volume_display,
            "issue_minimal_bonds_quantity_display": issue_minimal_bonds_quantity_display,
            "issue_display_title": issue_display_title,
        },
    )
