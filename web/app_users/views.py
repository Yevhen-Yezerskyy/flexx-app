# FILE: web/app_users/views.py  (обновлено — 2026-02-16)
# PURPOSE: Полный файл views: авторизация, регистрация, reset/set password + публичный endpoint Stückzinstabelle (с делением по годам).

from __future__ import annotations

import logging
from datetime import timedelta
from dateutil.relativedelta import relativedelta

from django.contrib.auth import get_user_model, login as auth_login
from django.contrib.auth.tokens import default_token_generator
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

from flexx.models import BondIssue
from flexx.contract_helpers import build_stueckzinsen_rows_for_issue
from flexx.emailer import (
    send_password_reset_email,
    send_registration_notify_email,
    send_registration_pending_email,
)

from .forms import (
    AgentRegistrationForm,
    ClientRegistrationForm,
    ForgotPasswordForm,
    ResetPasswordForm,
    LoginForm,
)

logger = logging.getLogger(__name__)
User = get_user_model()


# ---------------- AUTH ----------------

def _redirect_by_role(role: str) -> HttpResponse:
    if role == "admin":
        return redirect("/panel/admin/")
    if role == "agent":
        return redirect("/panel/tippgeber/")
    return redirect("/panel/client/")


def home(request: HttpRequest) -> HttpResponse:
    error = ""
    form = LoginForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        email = form.cleaned_data["email"]
        password = form.cleaned_data["password"]

        user = User.objects.filter(email__iexact=email).first()
        if user and user.check_password(password):
            if not user.is_active:
                error = "Benutzer gefunden. Wir warten auf die Aktivierung."
            else:
                auth_login(request, user, backend="django.contrib.auth.backends.ModelBackend")
                return _redirect_by_role(getattr(user, "role", "client"))
        else:
            error = "Login oder Passwort ist falsch."

    return render(request, "app_users/login.html", {"form": form, "error": error})


# ---------------- REGISTRATION ----------------

def register_client(request: HttpRequest) -> HttpResponse:
    form = ClientRegistrationForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        user = form.save()

        send_registration_pending_email(
            to_email=user.email,
            role=user.role,
            first_name=user.first_name,
            last_name=user.last_name,
        )

        send_registration_notify_email(
            role=user.role,
            user_email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
        )

        return render(request, "app_users/register_done.html", {"role": "client"})

    return render(request, "app_users/register_client.html", {"form": form})


def register_agent(request: HttpRequest) -> HttpResponse:
    form = AgentRegistrationForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        user = form.save()

        send_registration_pending_email(
            to_email=user.email,
            role=user.role,
            first_name=user.first_name,
            last_name=user.last_name,
        )

        send_registration_notify_email(
            role=user.role,
            user_email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
        )

        return render(request, "app_users/register_done.html", {"role": "tippgeber"})

    return render(request, "app_users/register_agent.html", {"form": form})


# ---------------- PASSWORD ----------------

def _build_user_link(request: HttpRequest, view_name: str, user, token: str) -> str:
    uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
    path = reverse(view_name, kwargs={"uidb64": uidb64, "token": token})
    return request.build_absolute_uri(path)


def forgot_password(request: HttpRequest) -> HttpResponse:
    msg = ""
    sent = False
    form = ForgotPasswordForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        sent = True
        email = form.cleaned_data["email"]
        user = User.objects.filter(email__iexact=email).first()

        if user:
            token = default_token_generator.make_token(user)
            link = _build_user_link(request, "password_reset", user, token)

            send_password_reset_email(
                to_email=user.email,
                first_name=user.first_name,
                last_name=user.last_name,
                reset_url=link,
            )

        msg = "Wenn die E-Mail existiert, wurde ein Link gesendet."

    return render(request, "app_users/password_forgot.html", {"form": form, "msg": msg, "sent": sent})


def reset_password(request: HttpRequest, uidb64: str, token: str) -> HttpResponse:
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.filter(pk=uid).first()
    except Exception:
        user = None

    if not user or not default_token_generator.check_token(user, token):
        return render(request, "app_users/password_reset.html", {"valid": False})

    form = ResetPasswordForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user.set_password(form.cleaned_data["password1"])
        user.save(update_fields=["password"])
        return render(request, "app_users/password_reset.html", {"valid": True, "done": True})

    return render(request, "app_users/password_reset.html", {"valid": True, "form": form})


def set_password(request: HttpRequest, uidb64: str, token: str) -> HttpResponse:
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.filter(pk=uid).first()
    except Exception:
        user = None

    if not user or not default_token_generator.check_token(user, token):
        return render(request, "app_users/password_set.html", {"invalid": True})

    form = ResetPasswordForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user.set_password(form.cleaned_data["password1"])
        user.is_active = True
        user.save(update_fields=["password", "is_active"])
        return redirect("/")

    return render(request, "app_users/password_set.html", {"form": form, "invalid": False})


# ---------------- PUBLIC INTEREST TABLE ----------------

def _split_rows_by_year(rows: list) -> list:
    if not rows:
        return []

    start = rows[0].pay_date
    end = rows[-1].pay_date

    if (end - start).days < 365:
        return [{"label": "", "rows": rows}]

    groups = []
    cur = start
    idx = 0

    while cur <= end:
        seg_start = cur
        seg_end = min(end, (cur + relativedelta(years=1)) - timedelta(days=1))

        seg_rows = []
        while idx < len(rows):
            d = rows[idx].pay_date
            if d < seg_start:
                idx += 1
                continue
            if d > seg_end:
                break
            seg_rows.append(rows[idx])
            idx += 1

        groups.append({
            "label": f"{seg_start:%d.%m.%Y} – {seg_end:%d.%m.%Y}",
            "rows": seg_rows
        })

        cur = seg_end + timedelta(days=1)

    return groups


def public_issue_interest_table(request: HttpRequest, issue_id: int) -> HttpResponse:
    issue = get_object_or_404(BondIssue, id=issue_id)

    rows = build_stueckzinsen_rows_for_issue(
        issue_date=issue.issue_date,
        term_months=issue.term_months,
        interest_rate_percent=issue.interest_rate,
        nominal_value=issue.bond_price,
        decimals=6,
        holiday_country="DE",
        holiday_subdiv=None,
    )

    rows = sorted(rows, key=lambda r: r.pay_date)
    raw_groups = _split_rows_by_year(rows)

    today = timezone.localdate()
    groups = []

    for g in raw_groups:
        rws = g["rows"]
        n = len(rws)
        per_col = (n + 2) // 3 if n else 0
        cols = [rws[i * per_col:(i + 1) * per_col] for i in range(3)] if per_col else [[], [], []]

        groups.append({
            "range_label": g["label"],
            "cols": cols
        })

    return render(
        request,
        "app_users/issue_interest_table.html",
        {
            "issue": issue,
            "groups": groups,
            "today": today,
        },
    )
