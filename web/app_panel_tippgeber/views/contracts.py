from __future__ import annotations

import base64
import binascii
from io import BytesIO
import os
import re

from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.db import transaction
from django.http import FileResponse, Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from PIL import Image, UnidentifiedImageError

from flexx.emailer import send_tippgeber_contract_signed_email
from flexx.models import BondIssue, FlexxlagerSignature, TippgeberContract
from flexx.pdf_tippgeber_contract import build_tippgeber_contract_text_pdf
from ..forms import TippgeberProfileForm
from .common import agent_only, get_missing_signed_issue_ids_for_tippgeber

SIGNED_CONTRACTS_SESSION_KEY = "panel_tippgeber_signed_contract_ids"


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


def _slugify_filename_part(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", value or "").strip("-") or "issue"


def _build_servicepartner_filename(issue: BondIssue, *, tippgeber_id: int) -> str:
    isin_wkn = (getattr(issue, "isin_wkn", "") or "").strip()
    middle = _slugify_filename_part(isin_wkn) if isin_wkn else "ohne-isin-wkn"
    return f"ServicepartnerVertrag-{middle}-N{tippgeber_id}.pdf"


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


def _is_tippgeber_profile_complete(user) -> bool:
    probe_form = TippgeberProfileForm(prefix="tipp", instance=user)
    for field_name, field in probe_form.fields.items():
        if not field.required:
            continue
        value = getattr(user, field_name, None)
        if value is None:
            return False
        if isinstance(value, str) and not value.strip():
            return False
    return True


def _fetch_missing_issues(user) -> list[BondIssue]:
    missing_issue_ids = get_missing_signed_issue_ids_for_tippgeber(user)
    if not missing_issue_ids:
        return []
    return list(BondIssue.objects.filter(id__in=missing_issue_ids, active=True).order_by("-issue_date", "-id"))


def _get_existing_contract_rows(user, issues: list[BondIssue]) -> dict[int, TippgeberContract]:
    issue_ids = [issue.id for issue in issues]
    if not issue_ids:
        return {}

    contracts_by_issue: dict[int, TippgeberContract] = {}
    existing = (
        TippgeberContract.objects.filter(tippgeber=user, issue_id__in=issue_ids)
        .select_related("issue")
        .order_by("-id")
    )
    for contract in existing:
        if contract.issue_id not in contracts_by_issue:
            contracts_by_issue[contract.issue_id] = contract

    return contracts_by_issue


def _sign_missing_contracts_for_tippgeber(
    *,
    user,
    signature_png: bytes,
) -> tuple[str | None, list[int]]:
    missing_issues = _fetch_missing_issues(user)
    if not missing_issues:
        return None, []
    contract_rows = _get_existing_contract_rows(user, missing_issues)
    now_dt = timezone.now()
    attachments: list[tuple[str, bytes, str]] = []
    saved_contract_ids: list[int] = []
    flexx_sign = FlexxlagerSignature.objects.first()
    company_signature_png = _read_file_field_bytes(flexx_sign.signature) if flexx_sign else None

    try:
        with transaction.atomic():
            for issue in missing_issues:
                contract = contract_rows.get(issue.id)
                if contract is None:
                    contract = TippgeberContract(tippgeber=user, issue=issue)
                if contract.signature_file:
                    contract.signature_file.delete(save=False)
                if contract.signed_contract_pdf:
                    contract.signed_contract_pdf.delete(save=False)

                contract.signature_file.save(
                    f"signature-IN{issue.id}-TG{user.id}.png",
                    ContentFile(signature_png),
                    save=False,
                )
                signed_pdf_res = build_tippgeber_contract_text_pdf(
                    issue=issue,
                    tippgeber=user,
                    tippgeber_signature_png=signature_png,
                    tippgeber_signature_line_text=(
                        f"{timezone.localdate():%d.%m.%Y} "
                        f"({(user.first_name or '').strip()} {(user.last_name or '').strip()})"
                    ).strip(),
                    company_signature_png=company_signature_png,
                    company_signature_line_text="(FleXXLager GmbH & Co. KG)",
                )
                pdf_filename = _build_servicepartner_filename(issue, tippgeber_id=user.id)
                contract.signed_contract_pdf.save(
                    pdf_filename,
                    ContentFile(signed_pdf_res.pdf_bytes),
                    save=False,
                )
                contract.signed_at = now_dt
                if contract.id:
                    contract.save(update_fields=["signature_file", "signed_contract_pdf", "signed_at", "updated_at"])
                else:
                    contract.save()
                if contract.id:
                    saved_contract_ids.append(contract.id)
                attachments.append((os.path.basename(contract.signed_contract_pdf.name), signed_pdf_res.pdf_bytes, "application/pdf"))
    except Exception as exc:
        return f"Vertraege konnten nicht gespeichert werden: {exc}", []

    if attachments:
        try:
            send_tippgeber_contract_signed_email(
                to_email=user.email or "",
                first_name=user.first_name or "",
                last_name=user.last_name or "",
                attachments=attachments,
            )
        except Exception:
            pass
    return None, saved_contract_ids


@login_required
def contract_preview(request: HttpRequest, issue_id: int) -> HttpResponse:
    denied = agent_only(request, allow_contracts_required_page=True)
    if denied:
        return denied
    if not _is_tippgeber_profile_complete(request.user):
        return redirect("/panel/tippgeber/contracts/required/")

    issue = BondIssue.objects.filter(id=issue_id, active=True).first()
    if not issue:
        raise Http404("Issue not found")

    missing_issue_ids = get_missing_signed_issue_ids_for_tippgeber(request.user)
    if issue.id not in missing_issue_ids:
        raise Http404("Contract preview is unavailable")

    pdf_result = build_tippgeber_contract_text_pdf(
        issue=issue,
        tippgeber=request.user,
    )
    filename = _build_servicepartner_filename(issue, tippgeber_id=request.user.id)
    return FileResponse(
        BytesIO(pdf_result.pdf_bytes),
        as_attachment=True,
        filename=filename,
        content_type="application/pdf",
    )


@login_required
def contracts_required(request: HttpRequest) -> HttpResponse:
    denied = agent_only(request, allow_contracts_required_page=True)
    if denied:
        return denied

    save_error = ""

    tipp_form = TippgeberProfileForm(prefix="tipp", instance=request.user)
    if request.method == "POST":
        action = (request.POST.get("action") or "save_profile").strip()
        tipp_form = TippgeberProfileForm(request.POST, prefix="tipp", instance=request.user)
        if tipp_form.is_valid():
            tipp_form.save()
            if action == "save_profile":
                return redirect("/panel/tippgeber/contracts/required/sign/")
        else:
            save_error = "Bitte pruefen Sie die markierten Felder."

    return render(
        request,
        "app_panel_tippgeber/contracts_required.html",
        {
            "tipp_form": tipp_form,
            "save_error": save_error,
        },
    )


@login_required
def contracts_required_sign(request: HttpRequest) -> HttpResponse:
    denied = agent_only(request, allow_contracts_required_page=True)
    if denied:
        return denied

    if not _is_tippgeber_profile_complete(request.user):
        return redirect("/panel/tippgeber/contracts/required/")

    sign_errors: list[str] = []
    info_message = ""
    done_mode = request.method == "GET" and request.GET.get("done") == "1"

    if done_mode:
        signed_ids = request.session.get(SIGNED_CONTRACTS_SESSION_KEY) or []
        if not isinstance(signed_ids, list):
            signed_ids = []
        signed_contracts = list(
            TippgeberContract.objects.select_related("issue")
            .filter(id__in=signed_ids, tippgeber=request.user)
            .order_by("-id")
        )
        signed_rows = []
        for c in signed_contracts:
            if not c.signed_contract_pdf:
                continue
            signed_rows.append({
                "url": c.signed_contract_pdf.url,
                "filename": os.path.basename(c.signed_contract_pdf.name),
            })
        return render(
            request,
            "app_panel_tippgeber/contracts_required_sign.html",
            {
                "done_mode": True,
                "signed_rows": signed_rows,
            },
        )

    missing_issues = _fetch_missing_issues(request.user)
    if not missing_issues:
        return redirect("/panel/tippgeber/")
    missing_issue_rows = [
        {
            "issue": issue,
            "preview_filename": _build_servicepartner_filename(issue, tippgeber_id=request.user.id),
        }
        for issue in missing_issues
    ]

    if request.method == "POST":
        action = (request.POST.get("action") or "").strip()
        if action == "sign_all":
            signature_data_url = request.POST.get("signature_png") or ""
            signature_raw = _decode_image_data_url(signature_data_url)
            if not signature_raw:
                sign_errors.append("Bitte laden Sie eine gueltige Signatur hoch oder zeichnen Sie eine.")
            signature_png = _normalize_signature_png(signature_raw) if signature_raw else None
            if signature_raw and not signature_png:
                sign_errors.append("Signaturbild konnte nicht verarbeitet werden.")
            if signature_png and not sign_errors:
                save_error, saved_contract_ids = _sign_missing_contracts_for_tippgeber(
                    user=request.user,
                    signature_png=signature_png,
                )
                if save_error:
                    sign_errors.append(save_error)
                else:
                    request.session[SIGNED_CONTRACTS_SESSION_KEY] = saved_contract_ids
                    request.session.modified = True
                    return redirect("/panel/tippgeber/contracts/required/sign/?done=1")

    return render(
        request,
        "app_panel_tippgeber/contracts_required_sign.html",
        {
            "done_mode": False,
            "missing_issues": missing_issues,
            "missing_issue_rows": missing_issue_rows,
            "sign_errors": sign_errors,
            "info_message": info_message,
        },
    )
