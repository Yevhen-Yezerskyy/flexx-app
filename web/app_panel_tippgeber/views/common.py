# FILE: web/app_panel_tippgeber/views/common.py  (новое — 2026-02-14)
# PURPOSE: Проверка роли agent и редирект в свою панель.

from __future__ import annotations
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect

from flexx.models import BondIssue, TippgeberContract

TIPPGEBER_CONTRACTS_REQUIRED_PATH = "/panel/tippgeber/contracts/required/"


def redirect_to_own_panel(role: str) -> HttpResponse:
    if role == "admin":
        return redirect("/panel/admin/")
    if role == "client":
        return redirect("/panel/client/")
    return redirect("/panel/tippgeber/")


def get_missing_signed_issue_ids_for_tippgeber(user) -> set[int]:
    if getattr(user, "role", None) != "agent":
        return set()
    active_issue_ids = set(BondIssue.objects.filter(active=True).values_list("id", flat=True))
    if not active_issue_ids:
        return set()
    signed_issue_ids = set(
        TippgeberContract.objects.filter(
            tippgeber=user,
            issue_id__in=active_issue_ids,
            signed_at__isnull=False,
        ).exclude(signed_contract_pdf="").values_list("issue_id", flat=True)
    )
    return active_issue_ids - signed_issue_ids


def has_all_signed_tippgeber_contracts(user) -> bool:
    return not get_missing_signed_issue_ids_for_tippgeber(user)


def agent_only(
    request: HttpRequest,
    *,
    allow_contracts_required_page: bool = False,
) -> HttpResponse | None:
    if getattr(request.user, "role", None) != "agent":
        return redirect_to_own_panel(getattr(request.user, "role", ""))
    if not allow_contracts_required_page and not has_all_signed_tippgeber_contracts(request.user):
        return redirect(TIPPGEBER_CONTRACTS_REQUIRED_PATH)
    return None
