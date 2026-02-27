# FILE: web/app_panel_tippgeber/views/issues.py  (новое — 2026-02-27)
# PURPOSE: Tippgeber: read-only список активных Emissionen (как в админе, без CRUD-действий).

from __future__ import annotations

from babel.numbers import format_decimal
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from flexx.models import BondIssue

from .common import agent_only


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


@login_required
def issues_list(request: HttpRequest) -> HttpResponse:
    denied = agent_only(request)
    if denied:
        return denied

    issues = (
        BondIssue.objects.filter(active=True)
        .prefetch_related("attachments")
        .all()
        .order_by("-issue_date", "-id")
    )
    for it in issues:
        it.bond_price_fmt = _format_decimal_de(it.bond_price, "#,##0.00")
        it.issue_volume_fmt = _format_decimal_de(it.issue_volume, "#,##0.00")
        it.minimal_bonds_quantity_fmt = _format_decimal_de(it.minimal_bonds_quantity, "#,##0")
        it.sorted_attachments = sorted(
            list(it.attachments.all()),
            key=lambda a: ((a.description or "").strip().lower(), a.id),
        )
        for a in it.sorted_attachments:
            filename = (a.file.name or "").rsplit("/", 1)[-1]
            a.short_filename = _shorten_middle_keep_ext(filename, max_len=42)

    return render(
        request,
        "app_panel_tippgeber/issues_list.html",
        {"issues": issues},
    )
