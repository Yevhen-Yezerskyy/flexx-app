# FILE: web/app_panel_admin/views/clients.py
# PURPOSE: Admin-Panel Kunden: список клиентов, их Verträge со статусами, toggle актив с confirm+email; delete (чистит TippgeberClient по client).

from __future__ import annotations

from urllib.parse import urlencode

from babel.numbers import format_decimal
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpRequest, HttpResponse, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from app_panel_admin.forms import AdminClientForm
from app_users.models import FlexxUser, TippgeberClient
from flexx.emailer import send_client_activated_email, send_client_deleted_email
from flexx.models import BondIssue, Contract

from .common import admin_only, build_set_password_url


def _contract_status_label(contract: Contract) -> str:
    if contract.paid_at:
        return "Bezahlt"
    if contract.signed_received_at:
        return "Signiert"
    if contract.contract_pdf:
        return "Erstellt"
    return "Unbekannt"


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


def _redirect_clients_list_with_notice(code: str) -> HttpResponse:
    base = reverse("panel_admin_clients")
    return redirect(f"{base}?{urlencode({'notice': code})}")


@login_required
def clients_list(request: HttpRequest) -> HttpResponse:
    denied = admin_only(request)
    if denied:
        return denied

    clients = FlexxUser.objects.filter(role=FlexxUser.Role.CLIENT).order_by("is_active", "-id")
    issues = _load_active_issues()
    selected_issue_id = issues[0].id if issues else None

    links = TippgeberClient.objects.filter(client__in=clients).select_related("client", "tippgeber").all()
    tip_by_client_id = {l.client_id: l.tippgeber for l in links if l.client_id}

    contracts = (
        Contract.objects.filter(client__in=clients)
        .select_related("issue", "client")
        .order_by("-id")
        .all()
    )
    contracts_by_client_id: dict[int, list[Contract]] = {}
    for c in contracts:
        c.status_label = _contract_status_label(c)
        contracts_by_client_id.setdefault(c.client_id, []).append(c)
    for client_contracts in contracts_by_client_id.values():
        can_delete_any = len(client_contracts) > 1
        for contract in client_contracts:
            contract.can_delete = can_delete_any and contract.status_label == "Unbekannt"

    rows = [
        {
            "u": c,
            "tippgeber": tip_by_client_id.get(c.id),
            "contracts": contracts_by_client_id.get(c.id, []),
        }
        for c in clients
    ]

    notice_code = (request.GET.get("notice") or "").strip()
    notice_text = ""
    if notice_code == "issue_required":
        notice_text = "Bitte wählen Sie eine Emission aus."
    elif notice_code == "issue_not_found":
        notice_text = "Die ausgewählte Emission ist nicht verfügbar."
    elif notice_code == "contract_delete_last_forbidden":
        notice_text = "Der letzte Vertrag kann nicht gelöscht werden."
    elif notice_code == "contract_delete_forbidden":
        notice_text = "Nur Verträge mit dem Status Unbekannt können gelöscht werden."

    return render(
        request,
        "app_panel_admin/clients_list.html",
        {
            "rows": rows,
            "issues": issues,
            "selected_issue_id": selected_issue_id,
            "notice_text": notice_text,
        },
    )


@login_required
def clients_create(request: HttpRequest) -> HttpResponse:
    denied = admin_only(request)
    if denied:
        return denied

    issues = _load_active_issues()
    selected_issue_id = issues[0].id if issues else None
    trigger_notify_confirm = False

    if request.method == "POST":
        issue_id_raw = (request.POST.get("issue_id") or "").strip()
        if issue_id_raw:
            try:
                selected_issue_id = int(issue_id_raw)
            except Exception:
                selected_issue_id = None
        form = AdminClientForm(request.POST, require_issue=True)
        if form.is_valid():
            issue = form.cleaned_data["issue"]
            is_active_selected = bool(form.cleaned_data.get("is_active"))
            notify_confirmed = request.POST.get("notify_confirmed") == "1"

            if is_active_selected and not notify_confirmed:
                trigger_notify_confirm = True
            else:
                created_client: FlexxUser | None = None
                with transaction.atomic():
                    obj: FlexxUser = form.save(commit=False)
                    obj.role = FlexxUser.Role.CLIENT
                    if not obj.pk:
                        obj.set_unusable_password()
                    obj.save()
                    created_client = obj

                    Contract.objects.create(
                        client=obj,
                        issue=issue,
                    )
                    _save_tippgeber_link(client=obj, tippgeber_id=form.cleaned_data.get("tippgeber_id"))

                if created_client and created_client.is_active and request.POST.get("notify") == "1":
                    set_password_url = ""
                    if not created_client.has_usable_password():
                        set_password_url = build_set_password_url(request, created_client)
                    send_client_activated_email(
                        to_email=created_client.email,
                        first_name=created_client.first_name or "",
                        last_name=created_client.last_name or "",
                        set_password_url=set_password_url,
                    )
                return redirect("panel_admin_clients")
    else:
        form = AdminClientForm(initial={"is_active": True}, require_issue=True)

    issue_error = form.errors.get("issue_id")
    return render(
        request,
        "app_panel_admin/clients_form.html",
        {
            "form": form,
            "mode": "create",
            "ask_notify_on_submit": False,
            "issues": issues,
            "selected_issue_id": selected_issue_id,
            "issue_error": issue_error[0] if issue_error else "",
            "trigger_notify_confirm": trigger_notify_confirm,
        },
    )


@login_required
def clients_edit(request: HttpRequest, user_id: int) -> HttpResponse:
    denied = admin_only(request)
    if denied:
        return denied

    user = get_object_or_404(FlexxUser, id=user_id, role=FlexxUser.Role.CLIENT)

    was_active = bool(user.is_active)

    if request.method == "POST":
        form = AdminClientForm(request.POST, instance=user, require_issue=False)
        if form.is_valid():
            obj: FlexxUser = form.save(commit=False)
            obj.role = FlexxUser.Role.CLIENT
            obj.save()

            if (not was_active) and obj.is_active and request.POST.get("notify") == "1":
                set_password_url = ""
                if not obj.has_usable_password():
                    set_password_url = build_set_password_url(request, obj)
                send_client_activated_email(
                    to_email=obj.email,
                    first_name=obj.first_name or "",
                    last_name=obj.last_name or "",
                    set_password_url=set_password_url,
                )

            _save_tippgeber_link(client=obj, tippgeber_id=form.cleaned_data.get("tippgeber_id"))
            return redirect("panel_admin_clients")
    else:
        form = AdminClientForm(instance=user, require_issue=False)

    return render(
        request,
        "app_panel_admin/clients_form.html",
        {"form": form, "mode": "edit", "user": user, "ask_notify_on_submit": (not was_active)},
    )


@login_required
def clients_add_contract(request: HttpRequest, user_id: int) -> HttpResponse:
    denied = admin_only(request)
    if denied:
        return denied

    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    client = get_object_or_404(FlexxUser, id=user_id, role=FlexxUser.Role.CLIENT)
    issue_id_raw = (request.POST.get("issue_id") or "").strip()
    if not issue_id_raw:
        return _redirect_clients_list_with_notice("issue_required")

    try:
        issue_id = int(issue_id_raw)
    except Exception:
        return _redirect_clients_list_with_notice("issue_not_found")

    issue = BondIssue.objects.filter(id=issue_id, active=True).first()
    if not issue:
        return _redirect_clients_list_with_notice("issue_not_found")

    Contract.objects.create(
        client=client,
        issue=issue,
    )
    return redirect("panel_admin_clients")


@login_required
def clients_delete_contract(request: HttpRequest, contract_id: int) -> HttpResponse:
    denied = admin_only(request)
    if denied:
        return denied

    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    contract = get_object_or_404(Contract.objects.select_related("client"), id=contract_id)
    if _contract_status_label(contract) != "Unbekannt":
        return _redirect_clients_list_with_notice("contract_delete_forbidden")

    contracts_count = Contract.objects.filter(client_id=contract.client_id).count()
    if contracts_count <= 1:
        return _redirect_clients_list_with_notice("contract_delete_last_forbidden")

    contract.delete()
    return redirect("panel_admin_clients")


@login_required
def clients_toggle_active(request: HttpRequest, user_id: int) -> HttpResponse:
    denied = admin_only(request)
    if denied:
        return denied

    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    user = get_object_or_404(FlexxUser, id=user_id, role=FlexxUser.Role.CLIENT)
    was_active = bool(user.is_active)
    user.is_active = not was_active
    user.save(update_fields=["is_active"])

    if (not was_active) and user.is_active and request.POST.get("notify") == "1":
        set_password_url = ""
        if not user.has_usable_password():
            set_password_url = build_set_password_url(request, user)
        send_client_activated_email(
            to_email=user.email,
            first_name=user.first_name or "",
            last_name=user.last_name or "",
            set_password_url=set_password_url,
        )

    return redirect("panel_admin_clients")


@login_required
def clients_delete(request: HttpRequest, user_id: int) -> HttpResponse:
    denied = admin_only(request)
    if denied:
        return denied

    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    user = get_object_or_404(FlexxUser, id=user_id, role=FlexxUser.Role.CLIENT)
    if request.POST.get("notify") == "1":
        send_client_deleted_email(
            to_email=user.email,
            first_name=user.first_name or "",
            last_name=user.last_name or "",
        )
    TippgeberClient.objects.filter(client=user).delete()
    user.delete()
    return redirect("panel_admin_clients")


def _save_tippgeber_link(*, client: FlexxUser, tippgeber_id: str | None) -> None:
    v = (tippgeber_id or "").strip()
    if not v:
        TippgeberClient.objects.filter(client=client).delete()
        return

    try:
        tid = int(v)
    except Exception:
        return

    tipp = FlexxUser.objects.filter(id=tid, role=FlexxUser.Role.AGENT).first()
    if not tipp:
        TippgeberClient.objects.filter(client=client).delete()
        return

    link = TippgeberClient.objects.filter(client=client).first()
    if not link:
        TippgeberClient.objects.create(client=client, tippgeber=tipp)
        return

    if link.tippgeber_id != tipp.id:
        link.tippgeber = tipp
        link.save(update_fields=["tippgeber"])
