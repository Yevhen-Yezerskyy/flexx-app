from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from babel.numbers import format_decimal
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render

from app_users.models import FlexxUser, TippgeberClient
from flexx.models import Contract, TippgeberContract

from .common import admin_only


def _format_decimal_de(value, fmt: str) -> str:
    try:
        return format_decimal(value, format=fmt, locale="de_DE")
    except Exception:
        return str(value or "")


def _client_contract_status(contract: Contract) -> tuple[str, str, object | None]:
    if contract.paid_at:
        return "Bezahlt", "Zahlungsdatum", contract.paid_at
    if contract.signed_received_at:
        return "Signiert", "Eingangsdatum", contract.signed_received_at
    if contract.contract_pdf:
        return "Erstellt", "Vertragsdatum", contract.contract_date
    return "Unbekannt", "", None


def _render_client_user_info(request: HttpRequest, target: FlexxUser) -> HttpResponse:
    link = (
        TippgeberClient.objects.filter(client=target)
        .select_related("tippgeber")
        .first()
    )
    contracts = list(
        Contract.objects.select_related("issue")
        .filter(client=target)
        .order_by("-id")
    )
    for contract in contracts:
        contract.status_label, contract.status_date_label, contract.status_date = _client_contract_status(contract)
        contract.total_amount = contract.nominal_amount_plus_percent
    return render(
        request,
        "app_panel_admin/_user_info_client.html",
        {
            "target": target,
            "tippgeber": link.tippgeber if link and link.tippgeber_id else None,
            "expected_investment_amount_display": (
                _format_decimal_de(link.expected_investment_amount, "#,##0.00")
                if link and link.tippgeber_id
                else ""
            ),
            "contracts": contracts,
        },
    )


def _render_tippgeber_user_info(request: HttpRequest, target: FlexxUser) -> HttpResponse:
    links = list(
        TippgeberClient.objects.filter(tippgeber=target)
        .select_related("client")
        .order_by("client__email")
    )
    clients = [link.client for link in links if link.client_id and link.client]
    client_ids = [client.id for client in clients]
    contracts = list(
        Contract.objects.select_related("issue", "client")
        .filter(client_id__in=client_ids)
        .order_by("-id")
    )
    contracts_by_client_id: dict[int, list[Contract]] = {}
    for contract in contracts:
        contracts_by_client_id.setdefault(contract.client_id, []).append(contract)

    clients_with_contracts: list[dict[str, object]] = []
    for client in clients:
        rows: list[dict[str, str]] = []
        for contract in contracts_by_client_id.get(client.id, []):
            sum_amount = contract.nominal_amount_plus_percent
            provision_base_amount = contract.nominal_amount
            provision_display = "—"
            if provision_base_amount is not None:
                provision = (
                    Decimal(str(provision_base_amount)) * Decimal(str(contract.issue.rate_tippgeber or 0)) / Decimal("100")
                ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                provision_vat = (provision * Decimal("0.19")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                provision_total = (provision + provision_vat).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                provision_display = _format_decimal_de(provision_total, "#,##0.00")
            status_label, _, _ = _client_contract_status(contract)
            rows.append(
                {
                    "issue_title": str(contract.issue),
                    "sum_display": (
                        _format_decimal_de(sum_amount, "#,##0.00")
                        if sum_amount is not None
                        else "—"
                    ),
                    "status_label": status_label,
                    "provision_display": provision_display,
                    "tippgeber_paid_label": "Bezahlt" if contract.tippgeber_paid_at else "Nicht bezahlt",
                    "client_paid_text": "bezahlt" if status_label == "Bezahlt" else "nicht bezahlt",
                    "tippgeber_paid_text": (
                        "bezahlt"
                        if contract.tippgeber_paid_at
                        else "nicht bezahlt"
                    ),
                }
            )
        clients_with_contracts.append({"client": client, "contracts": rows})

    signed_contracts = list(
        TippgeberContract.objects.select_related("issue")
        .filter(tippgeber=target)
        .exclude(signed_contract_pdf="")
        .order_by("-signed_at", "-id")
    )
    return render(
        request,
        "app_panel_admin/_user_info_tippgeber.html",
        {
            "target": target,
            "clients_with_contracts": clients_with_contracts,
            "signed_contracts": signed_contracts,
        },
    )


@login_required
def user_info_modal(request: HttpRequest, user_id: int) -> HttpResponse:
    denied = admin_only(request)
    if denied:
        return denied

    target = get_object_or_404(FlexxUser, id=user_id)
    if target.role == FlexxUser.Role.CLIENT:
        return _render_client_user_info(request, target)
    if target.role == FlexxUser.Role.AGENT:
        return _render_tippgeber_user_info(request, target)
    raise Http404("Unsupported user role")
