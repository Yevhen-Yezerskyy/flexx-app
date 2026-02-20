# FILE: web/app_panel_admin/views/common.py  (новое — 2026-02-14)
# PURPOSE: Общие хелперы для admin-panel views: role-guard + redirect.

from __future__ import annotations

from django.contrib.auth.tokens import default_token_generator
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode


def redirect_to_own_panel(role: str) -> HttpResponse:
    if role == "client":
        return redirect("/panel/client/")
    if role == "agent":
        return redirect("/panel/tippgeber/")
    return redirect("/panel/admin/")


def admin_only(request: HttpRequest) -> HttpResponse | None:
    if request.user.role != "admin":
        return redirect_to_own_panel(request.user.role)
    return None


def build_set_password_url(request: HttpRequest, user) -> str:
    token = default_token_generator.make_token(user)
    uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
    path = reverse("password_set", kwargs={"uidb64": uidb64, "token": token})
    return request.build_absolute_uri(path)
