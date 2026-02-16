# FILE: web/app_panel_admin/views/contracts.py  (обновлено — 2026-02-16)
# PURPOSE: Добавлена генерация PDF для сохранённого договора (action=pdf): build_contract_pdf → сохранить в Contract.pdf_file.

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation

from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from app_users.models import FlexxUser
from flexx.models import BondIssue, Contract
from flexx.contract_helpers import calc_contract_amounts_from_stueckzins_table
from flexx.pdf_contract import build_contract_pdf

from .common import admin_only


def _parse_iso_date(v: str) -> date | None:
    v = (v or "").strip()
    if not v:
        return None
    try:
        return date.fromisoformat(v)
    except Exception:
        return None


def _parse_decimal_2(v: str) -> Decimal | None:
    v = (v or "").strip()
    if not v:
        return None
    v = v.replace(",", ".")
    try:
        return Decimal(v).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return None


@login_required
def contracts_list(request: HttpRequest) -> HttpResponse:
    denied = admin_only(request)
    if denied:
        return denied

    contracts = (
        Contract.objects.select_related("client", "issue")
        .all()
        .order_by("-contract_date", "-id")
    )
    return render(request, "app_panel_admin/contracts_list.html", {"contracts": contracts})


@login_required
def contract_pick_issue(request: HttpRequest, user_id: int) -> HttpResponse:
    denied = admin_only(request)
    if denied:
        return denied

    client = get_object_or_404(FlexxUser, id=user_id, role=FlexxUser.Role.CLIENT)
    issues = BondIssue.objects.all().order_by("-issue_date", "-id")

    if request.method == "POST":
        issue_id_raw = (request.POST.get("issue_id") or "").strip()
        try:
            issue_id = int(issue_id_raw)
        except Exception:
            issue_id = 0

        issue = get_object_or_404(BondIssue, id=issue_id)

        c = Contract.objects.create(
            client=client,
            issue=issue,
            contract_date=timezone.localdate(),
        )
        return redirect("panel_admin_contract_edit", contract_id=c.id)

    selected_issue_id = issues[0].id if issues else None
    return render(
        request,
        "app_panel_admin/contract_pick_issue.html",
        {
            "client": client,
            "issues": issues,
            "selected_issue_id": selected_issue_id,
        },
    )


@login_required
def contract_edit(request: HttpRequest, contract_id: int) -> HttpResponse:
    denied = admin_only(request)
    if denied:
        return denied

    contract = get_object_or_404(
        Contract.objects.select_related("client", "issue"),
        id=contract_id,
    )
    issue = contract.issue

    errors: list[str] = []
    ok_message: str | None = None

    form_contract_date = contract.contract_date
    form_qty = contract.bonds_quantity or issue.minimal_bonds_quantity

    calc_result: dict[str, object] | None = None

    # UI state: empty | calc | saved
    mode = "saved" if (contract.nominal_amount_plus_percent and contract.settlement_date and contract.bonds_quantity) else "empty"

    if request.method == "POST":
        action = (request.POST.get("action") or "").strip()

        # --- PDF: только если уже сохранено ---
        if action == "pdf":
            if mode != "saved":
                errors.append("Bitte zuerst berechnen und speichern, dann PDF erzeugen.")
            else:
                res = build_contract_pdf(contract)
                contract.pdf_file.save(res.filename, ContentFile(res.pdf_bytes), save=True)
                ok_message = "PDF erstellt."
                return redirect("panel_admin_contract_edit", contract_id=contract.id)

        d = _parse_iso_date(request.POST.get("contract_date") or "")
        if d is None:
            errors.append("Bitte geben Sie das Datum der Unterzeichnung an.")
        else:
            form_contract_date = d

        qty_raw = (request.POST.get("bonds_quantity") or "").strip()
        try:
            qty = int(qty_raw)
        except Exception:
            qty = 0

        if qty < int(issue.minimal_bonds_quantity):
            errors.append(f"Anzahl der Anleihen muss mindestens {issue.minimal_bonds_quantity} sein.")
        else:
            form_qty = qty

        if not errors and action == "calc":
            settlement_date, nominal_amount, accrued_interest, total_amount = calc_contract_amounts_from_stueckzins_table(
                issue_date=issue.issue_date,
                term_months=issue.term_months,
                interest_rate_percent=issue.interest_rate,
                nominal_value=issue.bond_price,
                sign_date=form_contract_date,
                quantity=form_qty,
                banking_days_plus=10,
                holiday_country="DE",
                holiday_subdiv=None,
            )
            calc_result = {
                "settlement_date": settlement_date,
                "nominal_amount": nominal_amount,
                "accrued_interest": accrued_interest,
                "total_amount": total_amount,
            }
            mode = "calc"

        if not errors and action == "save":
            # save только после calc: берём hidden values
            settlement_date = _parse_iso_date(request.POST.get("calc_settlement_date") or "")
            nominal_amount = _parse_decimal_2(request.POST.get("calc_nominal_amount") or "")
            accrued_interest = _parse_decimal_2(request.POST.get("calc_accrued_interest") or "")
            total_amount = _parse_decimal_2(request.POST.get("calc_total_amount") or "")

            if settlement_date is None or nominal_amount is None or accrued_interest is None or total_amount is None:
                errors.append("Bitte zuerst berechnen, dann speichern.")
                mode = "empty"
            else:
                contract.contract_date = form_contract_date
                contract.settlement_date = settlement_date
                contract.bonds_quantity = form_qty
                contract.nominal_amount = nominal_amount
                contract.nominal_amount_plus_percent = total_amount
                contract.save(update_fields=[
                    "contract_date",
                    "settlement_date",
                    "bonds_quantity",
                    "nominal_amount",
                    "nominal_amount_plus_percent",
                    "updated_at",
                ])
                ok_message = "Gespeichert."
                calc_result = {
                    "settlement_date": settlement_date,
                    "nominal_amount": nominal_amount,
                    "accrued_interest": accrued_interest,
                    "total_amount": total_amount,
                }
                mode = "saved"

    # GET: показываем цифры только если уже сохранено (mode=saved)
    if calc_result is None and mode == "saved":
        accrued_interest = (Decimal(contract.nominal_amount_plus_percent) - Decimal(contract.nominal_amount)).quantize(Decimal("0.01"))
        calc_result = {
            "settlement_date": contract.settlement_date,
            "nominal_amount": Decimal(contract.nominal_amount).quantize(Decimal("0.01")),
            "accrued_interest": accrued_interest,
            "total_amount": Decimal(contract.nominal_amount_plus_percent).quantize(Decimal("0.01")),
        }

    return render(
        request,
        "app_panel_admin/contract_edit.html",
        {
            "contract": contract,
            "errors": errors,
            "ok_message": ok_message,
            "form_contract_date": form_contract_date,
            "form_qty": form_qty,
            "calc_result": calc_result,
            "min_qty": issue.minimal_bonds_quantity,
            "mode": mode,
        },
    )
