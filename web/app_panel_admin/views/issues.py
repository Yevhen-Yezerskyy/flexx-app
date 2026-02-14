# FILE: web/app_panel_admin/views/issues.py  (обновлено — 2026-02-14)
# PURPOSE: 1) Файлы: прокидываем request.FILES в BondIssueForm (create/edit);
#          2) Вывод: сортировка вложений по description (лейблу);
#          3) Имя файла: отдаём в шаблон уже "basename" (после последнего /).

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from app_panel_admin.forms import BondIssueForm
from flexx.models import BondIssue, BondIssueAttachment

from .common import admin_only


def _apply_attachments_post(issue: BondIssue, request: HttpRequest) -> None:
    for att in issue.attachments.all():
        if request.POST.get(f"att_del_{att.id}") == "1":
            att.delete()
            continue
        new_desc = request.POST.get(f"att_desc_{att.id}")
        if new_desc is not None and new_desc != att.description:
            att.description = new_desc[:255]
            att.save(update_fields=["description"])

    new_files = request.FILES.getlist("new_file")
    new_descs = request.POST.getlist("new_desc")
    for i, f in enumerate(new_files):
        desc = new_descs[i] if i < len(new_descs) else ""
        BondIssueAttachment.objects.create(
            issue=issue,
            file=f,
            description=(desc or "")[:255],
        )


@login_required
def issues_list(request: HttpRequest) -> HttpResponse:
    denied = admin_only(request)
    if denied:
        return denied

    issues = BondIssue.objects.all().order_by("-issue_date", "-id")
    return render(request, "app_panel_admin/issues_list.html", {"issues": issues})


@login_required
def issues_create(request: HttpRequest) -> HttpResponse:
    denied = admin_only(request)
    if denied:
        return denied

    if request.method == "POST":
        form = BondIssueForm(request.POST, request.FILES)  # <-- FIX
        if form.is_valid():
            issue = form.save()
            _apply_attachments_post(issue, request)
            return redirect("panel_admin_issues_list")
    else:
        copy_id = request.GET.get("copy")
        if copy_id:
            src = get_object_or_404(BondIssue, id=copy_id)
            form = BondIssueForm(
                initial={
                    "active": src.active,
                    "title": src.title,
                    "issue_date": src.issue_date,
                    "interest_rate": src.interest_rate,
                    "bond_price": src.bond_price,
                    "issue_volume": src.issue_volume,
                    "term_months": src.term_months,
                }
            )
            form.instance.contract = src.contract or {}
        else:
            form = BondIssueForm()

    return render(
        request,
        "app_panel_admin/issues_form.html",
        {"form": form, "mode": "create", "attachments": []},
    )


@login_required
def issues_edit(request: HttpRequest, issue_id: int) -> HttpResponse:
    denied = admin_only(request)
    if denied:
        return denied

    issue = get_object_or_404(BondIssue, id=issue_id)

    if request.method == "POST":
        form = BondIssueForm(request.POST, request.FILES, instance=issue)  # <-- FIX
        if form.is_valid():
            issue = form.save()
            _apply_attachments_post(issue, request)
            return redirect("panel_admin_issues_list")
    else:
        form = BondIssueForm(instance=issue)

    atts = issue.attachments.order_by("description", "id")
    attachments = [{"att": a, "filename": (a.file.name or "").rsplit("/", 1)[-1]} for a in atts]

    return render(
        request,
        "app_panel_admin/issues_form.html",
        {"form": form, "mode": "edit", "issue": issue, "attachments": attachments},
    )


@login_required
def issues_delete(request: HttpRequest, issue_id: int) -> HttpResponse:
    denied = admin_only(request)
    if denied:
        return denied

    issue = get_object_or_404(BondIssue, id=issue_id)
    if request.method == "POST":
        issue.delete()
    return redirect("panel_admin_issues_list")
