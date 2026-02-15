# FILE: web/app_panel_admin/views/contracts.py  (новое — 2026-02-15)
# PURPOSE: Admin contract flow: pick issue for client -> create Contract -> redirect to contract edit.

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from app_users.models import FlexxUser
from flexx.models import BondIssue, Contract

from .common import admin_only


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

    contract = get_object_or_404(Contract.objects.select_related("client", "issue"), id=contract_id)

    # Пока без логики редактирования: страница-заготовка.
    return render(
        request,
        "app_panel_admin/contract_edit.html",
        {
            "contract": contract,
        },
    )
