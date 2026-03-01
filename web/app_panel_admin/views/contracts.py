# FILE: web/app_panel_admin/views/contracts.py

from __future__ import annotations

from urllib.parse import urlencode

from babel.numbers import format_decimal
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.db import transaction
from django.http import HttpRequest, HttpResponse, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from app_users.models import TippgeberClient
from flexx.models import Contract
from flexx.pdf_contract import (
    build_contract_pdf_signed,
)
from flexx.emailer import (
    send_contract_paid_received_email,
    send_contract_signed_received_email,
)

from .common import admin_only


def _shorten_middle(name: str, max_len: int = 22) -> str:
    if len(name) <= max_len:
        return name
    keep_left = max_len // 2 - 2
    keep_right = max_len - keep_left - 3
    return f"{name[:keep_left]}...{name[-keep_right:]}"


def _format_decimal_de(value, fmt: str) -> str:
    try:
        return format_decimal(value, format=fmt, locale="de_DE")
    except Exception:
        return str(value)


def _redirect_contracts_list_with_notice(code: str) -> HttpResponse:
    base = reverse("panel_admin_contracts_list")
    return redirect(f"{base}?{urlencode({'notice': code})}")


@login_required
def contracts_list(request: HttpRequest) -> HttpResponse:
    denied = admin_only(request)
    if denied:
        return denied

    contracts = list(
        Contract.objects.select_related("client", "issue")
        .all()
        .order_by("-id")
    )
    client_ids = [c.client_id for c in contracts if c.client_id]
    links = (
        TippgeberClient.objects.filter(client_id__in=client_ids)
        .select_related("tippgeber")
        .all()
    )
    tip_by_client_id = {l.client_id: l.tippgeber for l in links if l.client_id}
    contract_count_by_client_id: dict[int, int] = {}
    for c in contracts:
        contract_count_by_client_id[c.client_id] = contract_count_by_client_id.get(c.client_id, 0) + 1

    for c in contracts:
        c.tippgeber = tip_by_client_id.get(c.client_id)
        if c.paid_at:
            c.status_stage = "paid"
        elif c.signed_received_at:
            c.status_stage = "signed_received"
        elif c.contract_pdf:
            c.status_stage = "created"
        else:
            c.status_stage = "not_created"
        c.can_delete = contract_count_by_client_id.get(c.client_id, 0) > 1
        c.issue_bond_price_display = _format_decimal_de(c.issue.bond_price, "#,##0.00")
        c.issue_volume_display = _format_decimal_de(c.issue.issue_volume, "#,##0.00")
        c.minimal_bonds_quantity_display = _format_decimal_de(c.issue.minimal_bonds_quantity, "#,##0")
        c.pdf_basename = c.contract_pdf.name.rsplit("/", 1)[-1] if c.contract_pdf else ""
        c.pdf_shortname = _shorten_middle(c.pdf_basename) if c.pdf_basename else ""
        c.signed_pdf_basename = (
            c.contract_pdf_signed.name.rsplit("/", 1)[-1]
            if c.contract_pdf_signed else ""
        )
        c.signed_pdf_shortname = (
            _shorten_middle(c.signed_pdf_basename)
            if c.signed_pdf_basename else ""
        )
        c.bonds_quantity_display = _format_decimal_de(c.bonds_quantity, "#,##0") if c.bonds_quantity is not None else ""
        c.nominal_amount_display = _format_decimal_de(c.nominal_amount, "#,##0.00") if c.nominal_amount is not None else ""
        c.nominal_amount_plus_percent_display = (
            _format_decimal_de(c.nominal_amount_plus_percent, "#,##0.00")
            if c.nominal_amount_plus_percent is not None else ""
        )
        c.accrued_interest_display = (
            _format_decimal_de(c.nominal_amount_plus_percent - c.nominal_amount, "#,##0.00")
            if c.nominal_amount is not None and c.nominal_amount_plus_percent is not None else ""
        )
        c.signed_signed_pdf_basename = (
            c.contract_pdf_signed_signed.name.rsplit("/", 1)[-1]
            if c.contract_pdf_signed_signed else ""
        )
        c.signed_signed_pdf_shortname = (
            _shorten_middle(c.signed_signed_pdf_basename)
            if c.signed_signed_pdf_basename else ""
        )

    notice_code = (request.GET.get("notice") or "").strip()
    notice_text = ""
    if notice_code == "mail_failed_status_changed":
        notice_text = "E-Mail wurde wegen technischer Probleme nicht versendet. Status wurde geändert."
    elif notice_code == "delete_last_forbidden":
        notice_text = "Der letzte Vertrag eines Kunden kann nicht gelöscht werden."
    elif notice_code == "paid_finalize_failed":
        notice_text = "Der Vertrag konnte technisch nicht finalisiert werden. Status wurde nicht geändert."

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
    paid_date = timezone.localdate()
    paid_email_attachments: list[tuple[str, bytes, str]] = []
    has_countersigned_contract = False

    try:
        with transaction.atomic():
            c.paid_at = None if was_set else paid_date
            c.save(update_fields=["paid_at", "updated_at"])

            if not was_set and c.contract_pdf_signed:
                signed_signed_res = build_contract_pdf_signed(c.id)
                if c.contract_pdf_signed_signed:
                    c.contract_pdf_signed_signed.delete(save=False)
                c.contract_pdf_signed_signed.save(
                    signed_signed_res.filename,
                    ContentFile(signed_signed_res.pdf_bytes),
                    save=False,
                )
                c.save(update_fields=["contract_pdf_signed_signed", "updated_at"])
                paid_email_attachments.append(
                    (signed_signed_res.filename, signed_signed_res.pdf_bytes, "application/pdf")
                )
                has_countersigned_contract = True
    except Exception:
        return _redirect_contracts_list_with_notice("paid_finalize_failed")

    if (not was_set) and c.paid_at and request.POST.get("notify") == "1":
        try:
            send_contract_paid_received_email(
                to_email=c.client.email,
                first_name=c.client.first_name or "",
                last_name=c.client.last_name or "",
                contract_id=c.id,
                issue_title=c.issue.title,
                paid_date=c.paid_at,
                has_countersigned_contract=has_countersigned_contract,
                attachments=paid_email_attachments,
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
    if Contract.objects.filter(client_id=c.client_id).count() <= 1:
        return _redirect_contracts_list_with_notice("delete_last_forbidden")
    c.delete()
    return redirect("panel_admin_contracts_list")
