# FILE: web/app_panel_client/views.py
# PURPOSE: Client panel reduced to one read-only page with the user's contracts.

from __future__ import annotations

import base64
import binascii
from datetime import date
from io import BytesIO
import os
import re

from babel.numbers import format_decimal
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from PIL import Image, UnidentifiedImageError

from flexx.contract_helpers import calc_contract_amounts_from_stueckzins_table
from flexx.emailer import (
    send_client_contract_created_email,
    send_client_contract_created_notify_email,
    send_client_contract_signed_email,
    send_client_contract_signed_notify_email,
)
from flexx.models import Contract
from flexx.pdf_contract import build_contract_pdf, build_contract_pdf_client_signed
from .forms import ClientBuyerDataForm


def _format_decimal_de(value, fmt: str) -> str:
    try:
        return format_decimal(value, format=fmt, locale="de_DE")
    except Exception:
        return str(value or "")


def _shorten_middle_keep_ext(name: str, max_len: int = 42) -> str:
    if len(name) <= max_len:
        return name
    if "." not in name:
        left = max_len // 2 - 2
        right = max_len - left - 3
        return f"{name[:left]}...{name[-right:]}"
    base, ext = name.rsplit(".", 1)
    ext = f".{ext}"
    budget = max_len - len(ext)
    if budget <= 3:
        return f"...{ext}"
    left = budget // 2 - 1
    right = budget - left - 3
    return f"{base[:left]}...{base[-right:]}{ext}"


def _redirect_to_own_panel(role: str) -> HttpResponse:
    if role == "admin":
        return redirect("/panel/admin/")
    if role == "agent":
        return redirect("/panel/tippgeber/")
    return redirect("/panel/client/")


def _client_only_or_redirect(request: HttpRequest) -> HttpResponse | None:
    if request.user.role != "client":
        return _redirect_to_own_panel(request.user.role)
    return None


def _contract_status_label(contract: Contract) -> str:
    if contract.paid_at:
        return "Bezahlt"
    if contract.signed_received_at:
        return "Signiert"
    if contract.contract_pdf and not contract.contract_pdf_signed and not contract.contract_pdf_signed_signed:
        return "Erstellt"
    return "Unbekannt"


def _client_contract_stage(contract: Contract) -> str:
    if contract.paid_at:
        return "paid"
    if contract.signed_received_at:
        return "signed"
    if contract.contract_pdf:
        return "created"
    return "unknown"


def _parse_iso_date(value: str) -> date | None:
    raw = (value or "").strip()
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except Exception:
        return None


def _build_consent_text(issue) -> str:
    return (
        f"Ich bestätige, die Unterlagen zur Emission {issue} erhalten, gelesen "
        f"und verstanden zu haben, insbesondere PIB Anleihe, PPM Anleihe und "
        f"Verbraucherinformationen Anleihe."
    )


def _build_calc_result(issue, contract_date: date, quantity: int) -> dict[str, object]:
    settlement_date, nominal_amount, accrued_interest, total_amount = calc_contract_amounts_from_stueckzins_table(
        issue_date=issue.issue_date,
        term_months=issue.term_months,
        interest_rate_percent=issue.interest_rate,
        nominal_value=issue.bond_price,
        sign_date=contract_date,
        quantity=quantity,
        banking_days_plus=10,
        holiday_country="DE",
        holiday_subdiv=None,
    )
    return {
        "settlement_date": settlement_date,
        "nominal_amount": nominal_amount,
        "accrued_interest": accrued_interest,
        "total_amount": total_amount,
    }


def _read_file_field_bytes(file_field) -> bytes | None:
    if not file_field:
        return None
    try:
        file_field.open("rb")
        return file_field.read()
    except Exception:
        return None
    finally:
        try:
            file_field.close()
        except Exception:
            pass


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


def _build_client_contract_email_payload(
    contract: Contract,
    *,
    primary_pdf_field_name: str,
) -> tuple[list[tuple[str, bytes, str]], str, bool]:
    attachments: list[tuple[str, bytes, str]] = []
    file_lines: list[str] = []
    has_contract_pdf = False

    primary_pdf_field = getattr(contract, primary_pdf_field_name)
    contract_pdf_bytes = _read_file_field_bytes(primary_pdf_field)
    contract_pdf_name = os.path.basename(primary_pdf_field.name) if primary_pdf_field else ""
    if contract_pdf_bytes and contract_pdf_name:
        attachments.append((contract_pdf_name, contract_pdf_bytes, "application/pdf"))
        has_contract_pdf = True

    issue_attachments = sorted(
        list(contract.issue.attachments.all()),
        key=lambda a: (((a.description or "").strip().lower()), a.id),
    )
    for attachment in issue_attachments:
        filename = os.path.basename(attachment.file.name or "")
        if not filename.lower().endswith(".pdf"):
            continue
        raw_bytes = _read_file_field_bytes(attachment.file)
        if not raw_bytes:
            continue
        description = (attachment.description or "").strip() or filename
        file_lines.append(f"* {description}")
        attachments.append((filename, raw_bytes, "application/pdf"))

    return attachments, "\n".join(file_lines), has_contract_pdf


def _get_client_contract_from_post(request: HttpRequest) -> Contract | None:
    contract_id_raw = (request.POST.get("contract_id") or "").strip()
    try:
        contract_id = int(contract_id_raw)
    except Exception:
        return None
    return (
        Contract.objects.select_related("issue", "client")
        .prefetch_related("issue__attachments")
        .filter(id=contract_id, client=request.user)
        .first()
    )


def _prepare_issue_display(issue) -> None:
    issue.bond_price_display = _format_decimal_de(issue.bond_price, "#,##0.00")
    issue.issue_volume_display = _format_decimal_de(issue.issue_volume, "#,##0.00")
    issue.minimal_bonds_quantity_display = _format_decimal_de(issue.minimal_bonds_quantity, "#,##0")
    issue.sorted_attachments = sorted(
        list(issue.attachments.all()),
        key=lambda a: ((a.description or "").strip().lower(), a.id),
    )
    for attachment in issue.sorted_attachments:
        filename = (attachment.file.name or "").rsplit("/", 1)[-1]
        attachment.short_filename = _shorten_middle_keep_ext(filename, max_len=42)


def _build_saved_calc_result(contract: Contract) -> dict[str, object]:
    return {
        "settlement_date": contract.settlement_date,
        "nominal_amount": contract.nominal_amount,
        "accrued_interest": (
            contract.nominal_amount_plus_percent - contract.nominal_amount
            if contract.nominal_amount is not None and contract.nominal_amount_plus_percent is not None
            else None
        ),
        "total_amount": contract.nominal_amount_plus_percent,
    }


def _render_contract_application_page(
    request: HttpRequest,
    contract: Contract,
    *,
    errors: list[str] | None = None,
    form_contract_date: date | None = None,
    form_qty: int | None = None,
    receipt_confirm_contract: bool = False,
    calc_result: dict[str, object] | None = None,
    show_finalize_modal: bool = False,
) -> HttpResponse:
    issue = contract.issue
    _prepare_issue_display(issue)

    finalized_view = bool(contract.contract_pdf)
    if form_contract_date is None:
        form_contract_date = contract.contract_date or timezone.localdate()
    if form_qty is None:
        form_qty = contract.bonds_quantity or issue.minimal_bonds_quantity
    if finalized_view and calc_result is None:
        calc_result = _build_saved_calc_result(contract)

    calc_nominal_display = None
    calc_accrued_display = None
    calc_total_display = None
    if calc_result:
        calc_nominal_display = _format_decimal_de(calc_result["nominal_amount"], "#,##0.00")
        calc_accrued_display = _format_decimal_de(calc_result["accrued_interest"], "#,##0.00")
        calc_total_display = _format_decimal_de(calc_result["total_amount"], "#,##0.00")
    contract_qty_display = _format_decimal_de(form_qty, "#,##0") if form_qty is not None else ""

    return render(
        request,
        "app_panel_client/contract_application.html",
        {
            "contract": contract,
            "consent_text": _build_consent_text(issue),
            "errors": errors or [],
            "today_date": timezone.localdate(),
            "form_contract_date": form_contract_date,
            "form_qty": form_qty,
            "min_qty": issue.minimal_bonds_quantity,
            "min_qty_display": issue.minimal_bonds_quantity_display,
            "calc_result": calc_result,
            "calc_nominal_display": calc_nominal_display,
            "calc_accrued_display": calc_accrued_display,
            "calc_total_display": calc_total_display,
            "contract_qty_display": contract_qty_display,
            "receipt_confirm_contract": receipt_confirm_contract,
            "finalized_view": finalized_view,
            "show_finalize_modal": show_finalize_modal,
            "contract_pdf_url": contract.contract_pdf.url if contract.contract_pdf else "",
            "contract_pdf_name": os.path.basename(contract.contract_pdf.name) if contract.contract_pdf else "",
        },
    )


def _render_contract_sign_page(
    request: HttpRequest,
    contract: Contract,
    *,
    sign_errors: list[str] | None = None,
) -> HttpResponse:
    _prepare_issue_display(contract.issue)

    form_contract_date = contract.contract_date
    contract_qty_display = (
        _format_decimal_de(contract.bonds_quantity, "#,##0")
        if contract.bonds_quantity is not None else ""
    )
    calc_nominal_display = (
        _format_decimal_de(contract.nominal_amount, "#,##0.00")
        if contract.nominal_amount is not None else "—"
    )
    calc_total_display = (
        _format_decimal_de(contract.nominal_amount_plus_percent, "#,##0.00")
        if contract.nominal_amount_plus_percent is not None else "—"
    )
    calc_accrued_display = "—"
    if contract.nominal_amount is not None and contract.nominal_amount_plus_percent is not None:
        calc_accrued_display = _format_decimal_de(
            contract.nominal_amount_plus_percent - contract.nominal_amount,
            "#,##0.00",
        )

    return render(
        request,
        "app_panel_client/contract_sign.html",
        {
            "contract": contract,
            "form_contract_date": form_contract_date,
            "contract_qty_display": contract_qty_display,
            "calc_nominal_display": calc_nominal_display,
            "calc_accrued_display": calc_accrued_display,
            "calc_total_display": calc_total_display,
            "issue_bond_price_display": contract.issue.bond_price_display,
            "issue_volume_display": contract.issue.issue_volume_display,
            "sign_errors": sign_errors or [],
            "show_signature_form": not contract.contract_pdf_signed,
            "signed_contract_pdf_url": contract.contract_pdf_signed.url if contract.contract_pdf_signed else "",
            "signed_contract_pdf_name": os.path.basename(contract.contract_pdf_signed.name) if contract.contract_pdf_signed else "",
        },
    )


@login_required
def contracts_list(request: HttpRequest) -> HttpResponse:
    denied = _client_only_or_redirect(request)
    if denied:
        return denied

    contracts = list(
        Contract.objects.select_related("issue")
        .prefetch_related("issue__attachments")
        .filter(client=request.user)
        .order_by("-id")
    )

    for contract in contracts:
        _prepare_issue_display(contract.issue)
        contract.status_label = _contract_status_label(contract)
        contract.client_stage = _client_contract_stage(contract)
        contract.issue_bond_price_display = contract.issue.bond_price_display
        contract.issue_volume_display = contract.issue.issue_volume_display
        contract.minimal_bonds_quantity_display = contract.issue.minimal_bonds_quantity_display
        contract.bonds_quantity_display = (
            _format_decimal_de(contract.bonds_quantity, "#,##0")
            if contract.bonds_quantity is not None else ""
        )
        contract.nominal_amount_display = (
            _format_decimal_de(contract.nominal_amount, "#,##0.00")
            if contract.nominal_amount is not None else ""
        )
        contract.nominal_amount_plus_percent_display = (
            _format_decimal_de(contract.nominal_amount_plus_percent, "#,##0.00")
            if contract.nominal_amount_plus_percent is not None else ""
        )
        contract.accrued_interest_display = (
            _format_decimal_de(contract.nominal_amount_plus_percent - contract.nominal_amount, "#,##0.00")
            if contract.nominal_amount is not None and contract.nominal_amount_plus_percent is not None else ""
        )
        contract.contract_pdf_basename = (
            os.path.basename(contract.contract_pdf.name)
            if contract.contract_pdf else ""
        )
        contract.contract_pdf_signed_basename = (
            os.path.basename(contract.contract_pdf_signed.name)
            if contract.contract_pdf_signed else ""
        )
        contract.contract_pdf_signed_signed_basename = (
            os.path.basename(contract.contract_pdf_signed_signed.name)
            if contract.contract_pdf_signed_signed else ""
        )

    return render(
        request,
        "app_panel_client/contracts_list.html",
        {"contracts": contracts},
    )


@login_required
def buyer_data(request: HttpRequest) -> HttpResponse:
    denied = _client_only_or_redirect(request)
    if denied:
        return denied

    if request.method != "POST":
        return redirect("panel_client_contracts_list")

    action = (request.POST.get("action") or "").strip()
    contract = _get_client_contract_from_post(request)
    if not contract or _contract_status_label(contract) != "Unbekannt":
        return redirect("panel_client_contracts_list")

    if action == "open":
        form = ClientBuyerDataForm(instance=request.user)
    else:
        form = ClientBuyerDataForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            return _render_contract_application_page(request, contract)

    return render(
        request,
        "app_panel_client/buyer_data_form.html",
        {
            "contract": contract,
            "form": form,
        },
    )


@login_required
def contract_application(request: HttpRequest) -> HttpResponse:
    denied = _client_only_or_redirect(request)
    if denied:
        return denied

    if request.method != "POST":
        return redirect("panel_client_contracts_list")

    action = (request.POST.get("action") or "open").strip()
    contract = _get_client_contract_from_post(request)
    if not contract:
        return redirect("panel_client_contracts_list")

    if action == "open":
        if not contract.contract_pdf and _contract_status_label(contract) != "Unbekannt":
            return redirect("panel_client_contracts_list")
        return _render_contract_application_page(request, contract)

    errors: list[str] = []
    form_contract_date = timezone.localdate()
    form_qty = contract.bonds_quantity or contract.issue.minimal_bonds_quantity
    receipt_confirm_contract = False
    calc_result: dict[str, object] | None = None
    show_finalize_modal = False

    if contract.contract_pdf:
        return _render_contract_application_page(request, contract)
    if _contract_status_label(contract) != "Unbekannt":
        return redirect("panel_client_contracts_list")

    receipt_confirm_contract = request.POST.get("receipt_confirm_contract") == "1"
    parsed_contract_date = _parse_iso_date(request.POST.get("contract_date") or "")
    if parsed_contract_date is None:
        errors.append("Bitte geben Sie das Datum des Vertragsabschlusses an.")
    else:
        form_contract_date = parsed_contract_date
        if form_contract_date < timezone.localdate():
            errors.append("Das Datum des Vertragsabschlusses darf nicht in der Vergangenheit liegen.")

    qty_raw = (request.POST.get("bonds_quantity") or "").strip()
    try:
        qty = int(qty_raw)
    except Exception:
        qty = 0

    if qty < int(contract.issue.minimal_bonds_quantity):
        errors.append(f"Anzahl der Anleihen muss mindestens {contract.issue.minimal_bonds_quantity} sein.")
    else:
        form_qty = qty

    if not errors:
        calc_result = _build_calc_result(contract.issue, form_contract_date, form_qty)

    if action in {"prepare_finalize", "finalize"} and not receipt_confirm_contract:
        errors.append("Bitte bestätigen Sie, dass Sie alle Unterlagen gelesen und verstanden haben.")

    if not errors and action == "prepare_finalize" and calc_result is not None:
        show_finalize_modal = True

    if not errors and action == "finalize" and calc_result is not None:
        if not contract.contract_pdf:
            with transaction.atomic():
                contract.contract_date = form_contract_date
                contract.settlement_date = calc_result["settlement_date"]
                contract.bonds_quantity = form_qty
                contract.nominal_amount = calc_result["nominal_amount"]
                contract.nominal_amount_plus_percent = calc_result["total_amount"]
                contract.save(update_fields=[
                    "contract_date",
                    "settlement_date",
                    "bonds_quantity",
                    "nominal_amount",
                    "nominal_amount_plus_percent",
                    "updated_at",
                ])
                pdf_result = build_contract_pdf(contract.id)
                if contract.contract_pdf:
                    contract.contract_pdf.delete(save=False)
                contract.contract_pdf.save(pdf_result.filename, ContentFile(pdf_result.pdf_bytes), save=True)
            attachments, file_decrs, has_contract_pdf = _build_client_contract_email_payload(
                contract,
                primary_pdf_field_name="contract_pdf",
            )
            if has_contract_pdf:
                try:
                    send_client_contract_created_email(
                        to_email=contract.client.email,
                        first_name=contract.client.first_name or "",
                        last_name=contract.client.last_name or "",
                        file_decrs=file_decrs,
                        attachments=attachments,
                    )
                except Exception:
                    pass
            try:
                send_client_contract_created_notify_email(
                    client_email=contract.client.email,
                    first_name=contract.client.first_name or "",
                    last_name=contract.client.last_name or "",
                    contract_id=contract.id,
                    issue_title=str(contract.issue),
                )
            except Exception:
                pass
            contract.refresh_from_db()
        return _render_contract_application_page(request, contract)

    return _render_contract_application_page(
        request,
        contract,
        errors=errors,
        form_contract_date=form_contract_date,
        form_qty=form_qty,
        receipt_confirm_contract=receipt_confirm_contract,
        calc_result=calc_result,
        show_finalize_modal=show_finalize_modal,
    )


@login_required
def contract_sign(request: HttpRequest) -> HttpResponse:
    denied = _client_only_or_redirect(request)
    if denied:
        return denied

    if request.method != "POST":
        return redirect("panel_client_contracts_list")

    action = (request.POST.get("action") or "").strip()
    contract = _get_client_contract_from_post(request)
    if not contract or not contract.contract_pdf:
        return redirect("panel_client_contracts_list")

    if action == "open":
        return _render_contract_sign_page(request, contract)
    if contract.contract_pdf_signed:
        return _render_contract_sign_page(request, contract)

    sign_errors: list[str] = []
    if action != "sign":
        sign_errors.append("Ungültige Aktion.")
        return _render_contract_sign_page(request, contract, sign_errors=sign_errors)

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
                    save=False,
                )
                contract.save(update_fields=[
                    "signature",
                    "updated_at",
                ])
                signed_contract_res = build_contract_pdf_client_signed(contract.id)
                if contract.contract_pdf_signed:
                    contract.contract_pdf_signed.delete(save=False)
                contract.contract_pdf_signed.save(
                    signed_contract_res.filename,
                    ContentFile(signed_contract_res.pdf_bytes),
                    save=False,
                )
                if not contract.signed_received_at:
                    contract.signed_received_at = timezone.localdate()
                contract.save(update_fields=[
                    "contract_pdf_signed",
                    "signed_received_at",
                    "updated_at",
                ])
        except Exception as exc:
            sign_errors.append(f"Signatur konnte nicht gespeichert werden: {exc}")
        else:
            contract.refresh_from_db()
            attachments, file_decrs, has_signed_pdf = _build_client_contract_email_payload(
                contract,
                primary_pdf_field_name="contract_pdf_signed",
            )
            if has_signed_pdf:
                try:
                    send_client_contract_signed_email(
                        to_email=contract.client.email,
                        first_name=contract.client.first_name or "",
                        last_name=contract.client.last_name or "",
                        file_decrs=file_decrs,
                        attachments=attachments,
                    )
                except Exception:
                    pass
            try:
                send_client_contract_signed_notify_email(
                    client_email=contract.client.email,
                    first_name=contract.client.first_name or "",
                    last_name=contract.client.last_name or "",
                    contract_id=contract.id,
                    issue_title=str(contract.issue),
                )
            except Exception:
                pass

    return _render_contract_sign_page(request, contract, sign_errors=sign_errors)
