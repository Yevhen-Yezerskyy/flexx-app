# FILE: web/app_panel_admin/views/contracts.py  (обновлено — 2026-02-16)
# PURPOSE: Добавлена генерация PDF для сохранённого договора (action=pdf): build_contract_pdf → сохранить в Contract.contract_pdf.

from __future__ import annotations

import base64
import binascii
from datetime import date
from decimal import Decimal, InvalidOperation
from io import BytesIO
import os
import re
from urllib.parse import urlencode

from babel.numbers import format_decimal
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.db import transaction
from django.http import HttpRequest, HttpResponse, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from PIL import Image, UnidentifiedImageError

from app_users.models import FlexxUser, TippgeberClient
from flexx.models import BondIssue, Contract
from flexx.contract_helpers import calc_contract_amounts_from_stueckzins_table
from flexx.pdf_contract import (
    build_contract_pdf,
    build_contract_pdf_signed,
    build_datenschutzeinwilligung_pdf,
    build_datenschutzeinwilligung_pdf_signed,
)
from flexx.emailer import (
    send_contract_paid_received_email,
    send_contract_signed_received_email,
)

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


def _shorten_middle(name: str, max_len: int = 22) -> str:
    if len(name) <= max_len:
        return name
    keep_left = max_len // 2 - 2
    keep_right = max_len - keep_left - 3
    return f"{name[:keep_left]}...{name[-keep_right:]}"


def _shorten_middle_keep_ext(name: str, max_len: int = 28) -> str:
    if len(name) <= max_len:
        return name
    base, ext = os.path.splitext(name)
    if not ext:
        return _shorten_middle(name, max_len=max_len)
    budget = max_len - len(ext)
    if budget <= 3:
        return f"...{ext}"
    keep_left = budget // 2 - 1
    keep_right = budget - keep_left - 3
    return f"{base[:keep_left]}...{base[-keep_right:]}{ext}"


def _format_decimal_de(value, fmt: str) -> str:
    try:
        return format_decimal(value, format=fmt, locale="de_DE")
    except Exception:
        return str(value)


def _redirect_contracts_list_with_notice(code: str) -> HttpResponse:
    base = reverse("panel_admin_contracts_list")
    return redirect(f"{base}?{urlencode({'notice': code})}")


def _extract_signature_template_text(issue_contract: dict) -> str:
    raw = str((issue_contract or {}).get("text_zwischen_3") or "")
    if not raw:
        return (
            "Ich bestätige, das Private Placement Memorandum und das "
            "Produktinformationsblatt erhalten zu haben. Ich bestätige, die "
            "Informationen für den Verbraucher mit der enthaltenen "
            "Widerrufsbelehrung erhalten zu haben."
        )

    raw = raw.replace("\r\n", "\n").replace("\r", "\n")
    parts = [re.sub(r"\s+", " ", p).strip() for p in raw.split("\n") if p.strip()]
    confirm_parts = [p for p in parts if p.lower().startswith("ich bestätige")]
    if len(confirm_parts) >= 2:
        selected = confirm_parts[:2]
    elif confirm_parts:
        selected = confirm_parts
    else:
        selected = parts[-2:] if len(parts) >= 2 else parts
    return " ".join(selected).strip()


def _decode_image_data_url(data_url: str) -> bytes | None:
    raw = (data_url or "").strip()
    if not raw:
        return None
    m = re.match(
        r"^data:image/(?:png|jpe?g|webp);base64,(?P<data>[A-Za-z0-9+/=\s]+)$",
        raw,
        flags=re.IGNORECASE,
    )
    if not m:
        return None
    b64 = re.sub(r"\s+", "", m.group("data"))
    try:
        return base64.b64decode(b64, validate=True)
    except (binascii.Error, ValueError):
        return None


def _normalize_signature_png(raw_bytes: bytes) -> bytes | None:
    try:
        with Image.open(BytesIO(raw_bytes)) as image:
            rgba = image.convert("RGBA")
            out = BytesIO()
            rgba.save(out, format="PNG")
            return out.getvalue()
    except (UnidentifiedImageError, OSError, ValueError):
        return None


@login_required
def contracts_list(request: HttpRequest) -> HttpResponse:
    denied = admin_only(request)
    if denied:
        return denied

    contracts = list(
        Contract.objects.select_related("client", "issue")
        .all()
        .order_by("-contract_date", "-id")
    )
    client_ids = [c.client_id for c in contracts if c.client_id]
    links = (
        TippgeberClient.objects.filter(client_id__in=client_ids)
        .select_related("tippgeber")
        .all()
    )
    tip_by_client_id = {l.client_id: l.tippgeber for l in links if l.client_id}

    for c in contracts:
        c.tippgeber = tip_by_client_id.get(c.client_id)
        c.pdf_basename = c.contract_pdf.name.rsplit("/", 1)[-1] if c.contract_pdf else ""
        c.pdf_shortname = _shorten_middle(c.pdf_basename) if c.pdf_basename else ""
        c.bonds_quantity_display = _format_decimal_de(c.bonds_quantity, "#,##0") if c.bonds_quantity is not None else ""
        c.nominal_amount_display = _format_decimal_de(c.nominal_amount, "#,##0.00") if c.nominal_amount is not None else ""
        c.nominal_amount_plus_percent_display = (
            _format_decimal_de(c.nominal_amount_plus_percent, "#,##0.00")
            if c.nominal_amount_plus_percent is not None else ""
        )

    notice_code = (request.GET.get("notice") or "").strip()
    notice_text = ""
    if notice_code == "mail_failed_status_changed":
        notice_text = "E-Mail wurde wegen technischer Probleme nicht versendet. Status wurde geändert."

    return render(
        request,
        "app_panel_admin/contracts_list.html",
        {"contracts": contracts, "notice_text": notice_text},
    )


@login_required
def contract_toggle_signed_received(request: HttpRequest, contract_id: int) -> HttpResponse:
    denied = admin_only(request)
    if denied:
        return denied
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    c = get_object_or_404(Contract.objects.select_related("client", "issue"), id=contract_id)
    was_set = c.signed_received_at is not None
    c.signed_received_at = None if was_set else timezone.localdate()
    c.save(update_fields=["signed_received_at", "updated_at"])

    if (not was_set) and c.signed_received_at and request.POST.get("notify") == "1":
        try:
            send_contract_signed_received_email(
                to_email=c.client.email,
                first_name=c.client.first_name or "",
                last_name=c.client.last_name or "",
                contract_id=c.id,
                issue_title=c.issue.title,
                signed_date=c.signed_received_at,
            )
        except Exception:
            return _redirect_contracts_list_with_notice("mail_failed_status_changed")
    return redirect("panel_admin_contracts_list")


@login_required
def contract_toggle_paid(request: HttpRequest, contract_id: int) -> HttpResponse:
    denied = admin_only(request)
    if denied:
        return denied
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    c = get_object_or_404(Contract.objects.select_related("client", "issue"), id=contract_id)
    was_set = c.paid_at is not None
    c.paid_at = None if was_set else timezone.localdate()
    c.save(update_fields=["paid_at", "updated_at"])

    if (not was_set) and c.paid_at and request.POST.get("notify") == "1":
        try:
            send_contract_paid_received_email(
                to_email=c.client.email,
                first_name=c.client.first_name or "",
                last_name=c.client.last_name or "",
                contract_id=c.id,
                issue_title=c.issue.title,
                paid_date=c.paid_at,
            )
        except Exception:
            return _redirect_contracts_list_with_notice("mail_failed_status_changed")
    return redirect("panel_admin_contracts_list")


@login_required
def contract_delete(request: HttpRequest, contract_id: int) -> HttpResponse:
    denied = admin_only(request)
    if denied:
        return denied
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    c = get_object_or_404(Contract, id=contract_id)
    c.delete()
    return redirect("panel_admin_contracts_list")


@login_required
def contract_pick_issue(request: HttpRequest, user_id: int) -> HttpResponse:
    denied = admin_only(request)
    if denied:
        return denied

    client = get_object_or_404(FlexxUser, id=user_id, role=FlexxUser.Role.CLIENT)
    tip_link = (
        TippgeberClient.objects.filter(client=client)
        .select_related("tippgeber")
        .first()
    )
    tippgeber = tip_link.tippgeber if tip_link and tip_link.tippgeber_id else None
    issues = BondIssue.objects.prefetch_related("attachments").all().order_by("-issue_date", "-id")
    for issue in issues:
        issue.bond_price_display = _format_decimal_de(issue.bond_price, "#,##0.00")
        issue.issue_volume_display = _format_decimal_de(issue.issue_volume, "#,##0.00")
        for a in issue.attachments.all():
            a.short_filename = _shorten_middle_keep_ext(a.filename, max_len=28)
    pick_error: str | None = None
    receipt_confirm_selected = False

    if request.method == "POST":
        issue_id_raw = (request.POST.get("issue_id") or "").strip()
        try:
            issue_id = int(issue_id_raw)
        except Exception:
            issue_id = 0

        issue = get_object_or_404(BondIssue, id=issue_id)
        receipt_confirm_selected = request.POST.get(f"receipt_confirm_{issue.id}") == "1"
        if not receipt_confirm_selected:
            pick_error = "Bitte bestätigen Sie die Empfangsbestätigung für die ausgewählte Emission."
        else:
            c = Contract.objects.create(
                client=client,
                issue=issue,
                contract_date=timezone.localdate(),
            )
            return redirect("panel_admin_contract_edit", contract_id=c.id)

        selected_issue_id = issue.id
        return render(
            request,
            "app_panel_admin/contract_pick_issue.html",
            {
                "client": client,
                "tippgeber": tippgeber,
                "issues": issues,
                "selected_issue_id": selected_issue_id,
                "pick_error": pick_error,
                "receipt_confirm_selected": receipt_confirm_selected,
            },
        )

    selected_issue_id = issues[0].id if issues else None
    return render(
        request,
        "app_panel_admin/contract_pick_issue.html",
        {
            "client": client,
            "tippgeber": tippgeber,
            "issues": issues,
            "selected_issue_id": selected_issue_id,
            "pick_error": pick_error,
            "receipt_confirm_selected": receipt_confirm_selected,
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
    tip_link = (
        TippgeberClient.objects.filter(client=contract.client)
        .select_related("tippgeber")
        .first()
    )
    tippgeber = tip_link.tippgeber if tip_link and tip_link.tippgeber_id else None

    errors: list[str] = []
    ok_message: str | None = None
    saved_pdf_url: str | None = contract.contract_pdf.url if contract.contract_pdf else None
    saved_pdf_name: str | None = (
        contract.contract_pdf.name.rsplit("/", 1)[-1] if contract.contract_pdf else None
    )
    saved_dsgvo_pdf_url: str | None = (
        contract.datenschutzeinwilligung_pdf.url if contract.datenschutzeinwilligung_pdf else None
    )
    saved_dsgvo_pdf_name: str | None = (
        contract.datenschutzeinwilligung_pdf.name.rsplit("/", 1)[-1]
        if contract.datenschutzeinwilligung_pdf else None
    )

    form_contract_date = contract.contract_date
    form_qty = contract.bonds_quantity or issue.minimal_bonds_quantity

    calc_result: dict[str, object] | None = None

    # UI state: empty | calc | saved
    mode = "saved" if (contract.nominal_amount_plus_percent and contract.settlement_date and contract.bonds_quantity) else "empty"
    receipt_confirm_contract = False

    if request.method == "POST":
        action = (request.POST.get("action") or "").strip()
        receipt_confirm_contract = request.POST.get("receipt_confirm_contract") == "1"

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

        if not errors and action in {"save", "save_pdf"}:
            if action == "save_pdf" and not receipt_confirm_contract:
                errors.append("Bitte bestätigen Sie die Empfangsbestätigung.")
                mode = "calc"

        if not errors and action in {"save", "save_pdf"}:
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
                if action == "save_pdf":
                    res = build_contract_pdf(contract.id)
                    dsgvo_res = build_datenschutzeinwilligung_pdf(contract.id)
                    if contract.contract_pdf:
                        contract.contract_pdf.delete(save=False)
                    if contract.datenschutzeinwilligung_pdf:
                        contract.datenschutzeinwilligung_pdf.delete(save=False)
                    contract.contract_pdf.save(res.filename, ContentFile(res.pdf_bytes), save=True)
                    contract.datenschutzeinwilligung_pdf.save(
                        dsgvo_res.filename,
                        ContentFile(dsgvo_res.pdf_bytes),
                        save=True,
                    )
                    ok_message = "Gespeichert und PDF erstellt."
                    saved_pdf_url = contract.contract_pdf.url
                    saved_pdf_name = res.filename
                    saved_dsgvo_pdf_url = contract.datenschutzeinwilligung_pdf.url
                    saved_dsgvo_pdf_name = dsgvo_res.filename
                else:
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

    issue_bond_price_display = _format_decimal_de(issue.bond_price, "#,##0.00")
    issue_volume_display = _format_decimal_de(issue.issue_volume, "#,##0.00")
    min_qty_display = _format_decimal_de(issue.minimal_bonds_quantity, "#,##0")
    calc_nominal_display = None
    calc_accrued_display = None
    calc_total_display = None
    if calc_result:
        calc_nominal_display = _format_decimal_de(calc_result["nominal_amount"], "#,##0.00")
        calc_accrued_display = _format_decimal_de(calc_result["accrued_interest"], "#,##0.00")
        calc_total_display = _format_decimal_de(calc_result["total_amount"], "#,##0.00")

    return render(
        request,
        "app_panel_admin/contract_edit.html",
        {
            "contract": contract,
            "tippgeber": tippgeber,
            "errors": errors,
            "ok_message": ok_message,
            "saved_pdf_url": saved_pdf_url,
            "saved_pdf_name": saved_pdf_name,
            "saved_dsgvo_pdf_url": saved_dsgvo_pdf_url,
            "saved_dsgvo_pdf_name": saved_dsgvo_pdf_name,
            "form_contract_date": form_contract_date,
            "form_qty": form_qty,
            "calc_result": calc_result,
            "min_qty": issue.minimal_bonds_quantity,
            "min_qty_display": min_qty_display,
            "issue_bond_price_display": issue_bond_price_display,
            "issue_volume_display": issue_volume_display,
            "calc_nominal_display": calc_nominal_display,
            "calc_accrued_display": calc_accrued_display,
            "calc_total_display": calc_total_display,
            "mode": mode,
            "receipt_confirm_contract": receipt_confirm_contract,
        },
    )


@login_required
def contract_unterschreiben(request: HttpRequest, contract_id: int) -> HttpResponse:
    denied = admin_only(request)
    if denied:
        return denied

    contract = get_object_or_404(
        Contract.objects.select_related("client", "issue"),
        id=contract_id,
    )
    tip_link = (
        TippgeberClient.objects.filter(client=contract.client)
        .select_related("tippgeber")
        .first()
    )
    tippgeber = tip_link.tippgeber if tip_link and tip_link.tippgeber_id else None

    issue = contract.issue
    issue_contract = issue.contract if isinstance(issue.contract, dict) else {}
    signature_template_text = _extract_signature_template_text(issue_contract)
    issue_bond_price_display = _format_decimal_de(issue.bond_price, "#,##0.00")
    issue_volume_display = _format_decimal_de(issue.issue_volume, "#,##0.00")

    calc_nominal_display = "—"
    calc_accrued_display = "—"
    calc_total_display = "—"
    sign_errors: list[str] = []
    sign_ok_message: str | None = None

    if contract.nominal_amount is not None:
        calc_nominal_display = _format_decimal_de(contract.nominal_amount, "#,##0.00")
    if contract.nominal_amount_plus_percent is not None:
        calc_total_display = _format_decimal_de(contract.nominal_amount_plus_percent, "#,##0.00")
    if contract.nominal_amount is not None and contract.nominal_amount_plus_percent is not None:
        accrued_interest = (
            Decimal(contract.nominal_amount_plus_percent) - Decimal(contract.nominal_amount)
        ).quantize(Decimal("0.01"))
        calc_accrued_display = _format_decimal_de(accrued_interest, "#,##0.00")

    if request.method == "POST":
        action = (request.POST.get("action") or "").strip()
        if action != "sign":
            sign_errors.append("Ungültige Aktion.")
        else:
            signature_data_url = request.POST.get("signature_png") or ""
            signature_raw = _decode_image_data_url(signature_data_url)
            if not signature_raw:
                sign_errors.append("Bitte laden Sie eine gültige Signatur hoch oder zeichnen Sie eine.")
            signature_png = _normalize_signature_png(signature_raw) if signature_raw else None
            if signature_raw and not signature_png:
                sign_errors.append("Signaturbild konnte nicht verarbeitet werden.")

            if not sign_errors and signature_png:
                try:
                    with transaction.atomic():
                        if contract.signature:
                            contract.signature.delete(save=False)
                        contract.signature.save(
                            f"signature-IN{contract.id}.png",
                            ContentFile(signature_png),
                            save=True,
                        )

                        signed_contract_res = build_contract_pdf_signed(contract.id)
                        signed_dsgvo_res = build_datenschutzeinwilligung_pdf_signed(contract.id)

                        if contract.contract_pdf_signed:
                            contract.contract_pdf_signed.delete(save=False)
                        if contract.datenschutzeinwilligung_pdf_signed:
                            contract.datenschutzeinwilligung_pdf_signed.delete(save=False)

                        contract.contract_pdf_signed.save(
                            signed_contract_res.filename,
                            ContentFile(signed_contract_res.pdf_bytes),
                            save=False,
                        )
                        contract.datenschutzeinwilligung_pdf_signed.save(
                            signed_dsgvo_res.filename,
                            ContentFile(signed_dsgvo_res.pdf_bytes),
                            save=False,
                        )
                        contract.save(update_fields=[
                            "contract_pdf_signed",
                            "datenschutzeinwilligung_pdf_signed",
                            "updated_at",
                        ])
                except Exception as exc:
                    sign_errors.append(f"Signatur konnte nicht gespeichert werden: {exc}")
                else:
                    sign_ok_message = "Signierte Verträge wurden erfolgreich gespeichert."
                    contract.refresh_from_db()

    signed_contract_pdf_url: str | None = (
        contract.contract_pdf_signed.url if contract.contract_pdf_signed else None
    )
    signed_contract_pdf_name: str | None = (
        contract.contract_pdf_signed.name.rsplit("/", 1)[-1]
        if contract.contract_pdf_signed else None
    )
    signed_dsgvo_pdf_url: str | None = (
        contract.datenschutzeinwilligung_pdf_signed.url
        if contract.datenschutzeinwilligung_pdf_signed else None
    )
    signed_dsgvo_pdf_name: str | None = (
        contract.datenschutzeinwilligung_pdf_signed.name.rsplit("/", 1)[-1]
        if contract.datenschutzeinwilligung_pdf_signed else None
    )
    show_signature_form = not (signed_contract_pdf_url or signed_dsgvo_pdf_url)

    return render(
        request,
        "app_panel_admin/contract_unterschreiben.html",
        {
            "contract": contract,
            "tippgeber": tippgeber,
            "issue_bond_price_display": issue_bond_price_display,
            "issue_volume_display": issue_volume_display,
            "signature_template_text": signature_template_text,
            "calc_nominal_display": calc_nominal_display,
            "calc_accrued_display": calc_accrued_display,
            "calc_total_display": calc_total_display,
            "sign_errors": sign_errors,
            "sign_ok_message": sign_ok_message,
            "signed_contract_pdf_url": signed_contract_pdf_url,
            "signed_contract_pdf_name": signed_contract_pdf_name,
            "signed_dsgvo_pdf_url": signed_dsgvo_pdf_url,
            "signed_dsgvo_pdf_name": signed_dsgvo_pdf_name,
            "show_signature_form": show_signature_form,
        },
    )
