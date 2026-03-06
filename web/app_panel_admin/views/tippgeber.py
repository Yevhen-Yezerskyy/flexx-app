# FILE: web/app_panel_admin/views/tippgeber.py  (обновлено — 2026-02-15)
# PURPOSE: Admin-Panel: Tippgeber list (с его Kunden), edit/delete, POST toggle aktiv/inaktiv с confirm-уведомлением по email при активации.

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from babel.numbers import format_decimal
from django.db import transaction
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render

from app_panel_admin.forms import AdminTippgeberForm
from app_users.models import FlexxUser, TippgeberClient
from flexx.emailer import send_tippgeber_activated_email, send_tippgeber_deleted_email
from flexx.models import Contract

from .common import admin_only, build_set_password_url


def _format_decimal_de(value, fmt: str) -> str:
    try:
        return format_decimal(value, format=fmt, locale="de_DE")
    except Exception:
        return str(value or "")


def _contract_status_label(contract: Contract) -> str:
    if contract.paid_at:
        return "Bezahlt"
    if contract.signed_received_at:
        return "Signiert"
    if contract.contract_pdf:
        return "Erstellt"
    return "Unbekannt"


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

    all_clients: list[FlexxUser] = []
    for grouped in clients_by_tip_id.values():
        all_clients.extend(grouped)
    client_ids = [c.id for c in all_clients]
    contracts = list(
        Contract.objects.select_related("issue", "client")
        .filter(client_id__in=client_ids)
        .order_by("-id")
    )
    contracts_by_client_id: dict[int, list[Contract]] = {}
    for contract in contracts:
        contracts_by_client_id.setdefault(contract.client_id, []).append(contract)

    rows = []
    for t in tips:
        clients = []
        for client in clients_by_tip_id.get(t.id, []):
            contract_summaries: list[dict[str, str]] = []
            for contract in contracts_by_client_id.get(client.id, []):
                issue_date_display = contract.issue.issue_date.strftime("%d.%m.%Y") if contract.issue.issue_date else "—"
                sum_amount = contract.nominal_amount_plus_percent
                amount_display = _format_decimal_de(sum_amount, "#,##0.00") if sum_amount is not None else "—"
                provision_base_amount = contract.nominal_amount
                provision_display = "—"
                if provision_base_amount is not None:
                    provision = (
                        Decimal(str(provision_base_amount)) * Decimal(str(contract.issue.rate_tippgeber or 0)) / Decimal("100")
                    ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                    provision_vat = (provision * Decimal("0.19")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                    provision_total = (provision + provision_vat).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                    provision_display = _format_decimal_de(provision_total, "#,##0.00")
                contract_summaries.append(
                    {
                        "issue_date_display": issue_date_display,
                        "amount_display": amount_display,
                        "client_paid_text": "bezahlt" if _contract_status_label(contract) == "Bezahlt" else "nicht bezahlt",
                        "provision_display": provision_display,
                        "tippgeber_paid_text": "bezahlt" if contract.tippgeber_paid_at else "nicht bezahlt",
                    }
                )
            clients.append({"u": client, "contract_summaries": contract_summaries})
        rows.append({"u": t, "clients": clients})

    return render(request, "app_panel_admin/tippgeber_list.html", {"rows": rows})


@login_required
def tippgeber_edit(request: HttpRequest, user_id: int) -> HttpResponse:
    denied = admin_only(request)
    if denied:
        return denied

    user = get_object_or_404(FlexxUser, id=user_id, role=FlexxUser.Role.AGENT)

    def _linked_clients_rows() -> list[dict]:
        links = (
            TippgeberClient.objects.filter(tippgeber=user, client__isnull=False)
            .select_related("client")
            .order_by("client__last_name", "client__first_name", "client__email")
        )
        rows: list[dict] = []
        for link in links:
            if not link.client_id:
                continue
            rows.append({"link_id": link.id, "client": link.client})
        return rows

    if request.method == "POST":
        form = AdminTippgeberForm(request.POST, instance=user)
        if form.is_valid():
            unlink_client_ids_raw = request.POST.getlist("unlink_client_ids")
            unlink_client_ids: list[int] = []
            for v in unlink_client_ids_raw:
                try:
                    unlink_client_ids.append(int(v))
                except (TypeError, ValueError):
                    continue

            with transaction.atomic():
                obj: FlexxUser = form.save(commit=False)
                obj.role = FlexxUser.Role.AGENT
                obj.save()
                if unlink_client_ids:
                    TippgeberClient.objects.filter(
                        tippgeber=obj,
                        client_id__in=unlink_client_ids,
                    ).delete()
            return redirect("panel_admin_tippgeber_list")
    else:
        form = AdminTippgeberForm(instance=user)

    return render(
        request,
        "app_panel_admin/tippgeber_form.html",
        {"form": form, "user": user, "linked_clients": _linked_clients_rows()},
    )


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
