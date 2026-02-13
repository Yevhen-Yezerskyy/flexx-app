# FILE: web/app_users/views.py  (обновлено — 2026-02-13)
# PURPOSE: Фикс reset_password: всегда отдаём контекст с `valid` (вместо `invalid`), чтобы ссылка не считалась “невалидной” из-за несовпадения имён в шаблоне; после успешной смены пароля показываем done=True.

from __future__ import annotations

import logging

from django.contrib.auth import get_user_model, login as auth_login
from django.contrib.auth.tokens import default_token_generator
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

from flexx.emailer import (
    send_password_reset_email,
    send_registration_notify_email,
    send_registration_pending_email,
    send_set_password_email,
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


def _build_user_link(request: HttpRequest, *, view_name: str, user, token: str) -> str:
    uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
    path = reverse(view_name, kwargs={"uidb64": uidb64, "token": token})
    return request.build_absolute_uri(path)


def _redirect_by_role(role: str) -> HttpResponse:
    if role == "admin":
        return redirect("/panel/admin/")
    if role == "agent":
        return redirect("/panel/tippgeber/")
    return redirect("/panel/client/")


def home(request: HttpRequest) -> HttpResponse:
    error = ""
    form = LoginForm(request.POST or None)

    if request.method == "POST":
        if form.is_valid():
            email = form.cleaned_data["email"]
            password = form.cleaned_data["password"]

            user = User.objects.filter(email__iexact=email).first()

            if user and user.check_password(password):
                if not user.is_active:
                    error = "Benutzer gefunden. Wir warten auf die Aktivierung."
                    logger.info("LOGIN pending_activation email=%s role=%s", user.email, getattr(user, "role", ""))
                else:
                    auth_login(request, user, backend="django.contrib.auth.backends.ModelBackend")
                    logger.info("LOGIN ok email=%s role=%s", user.email, getattr(user, "role", ""))
                    return _redirect_by_role(getattr(user, "role", "client"))
            else:
                error = "Login oder Passwort ist falsch."
                logger.info("LOGIN bad_credentials email=%s", email)

    return render(request, "app_users/login.html", {"form": form, "error": error})


def register_client(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = ClientRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()

            mail_user_ok = send_registration_pending_email(
                to_email=user.email,
                role=user.role,
                first_name=user.first_name,
                last_name=user.last_name,
            )
            mail_notify_ok = send_registration_notify_email(
                role=user.role,
                user_email=user.email,
                first_name=user.first_name,
                last_name=user.last_name,
            )

            logger.info(
                "REGISTER client email=%s user_mail=%s notify_mail=%s active=%s",
                user.email,
                mail_user_ok,
                mail_notify_ok,
                user.is_active,
            )
            return render(request, "app_users/register_done.html", {"role": "client"})
    else:
        form = ClientRegistrationForm()

    return render(request, "app_users/register_client.html", {"form": form})


def register_agent(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = AgentRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()

            mail_user_ok = send_registration_pending_email(
                to_email=user.email,
                role=user.role,
                first_name=user.first_name,
                last_name=user.last_name,
            )
            mail_notify_ok = send_registration_notify_email(
                role=user.role,
                user_email=user.email,
                first_name=user.first_name,
                last_name=user.last_name,
            )

            logger.info(
                "REGISTER agent email=%s user_mail=%s notify_mail=%s active=%s",
                user.email,
                mail_user_ok,
                mail_notify_ok,
                user.is_active,
            )
            return render(request, "app_users/register_done.html", {"role": "tippgeber"})
    else:
        form = AgentRegistrationForm()

    return render(request, "app_users/register_agent.html", {"form": form})


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
            link = _build_user_link(request, view_name="password_reset", user=user, token=token)

            ok = send_password_reset_email(
                to_email=user.email,
                first_name=user.first_name,
                last_name=user.last_name,
                reset_url=link,
            )
            logger.info("FORGOT_PASSWORD lookup email=%s found=True mail=%s", email, ok)
        else:
            logger.info("FORGOT_PASSWORD lookup email=%s found=False", email)

        msg = "Wenn die E-Mail existiert, wurde ein Link gesendet."

    return render(request, "app_users/password_forgot.html", {"form": form, "msg": msg, "sent": sent})


def reset_password(request: HttpRequest, uidb64: str, token: str) -> HttpResponse:
    user = None
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.filter(pk=uid).first()
    except Exception:
        user = None

    if not user or not default_token_generator.check_token(user, token):
        logger.info("RESET_PASSWORD invalid uidb64=%s", uidb64)
        return render(request, "app_users/password_reset.html", {"valid": False, "email": "", "done": False})

    form = ResetPasswordForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user.set_password(form.cleaned_data["password1"])
        user.save(update_fields=["password"])
        logger.info("RESET_PASSWORD done email=%s", user.email)
        return render(
            request,
            "app_users/password_reset.html",
            {"valid": True, "email": user.email, "form": form, "done": True},
        )

    return render(
        request,
        "app_users/password_reset.html",
        {"valid": True, "email": user.email, "form": form, "done": False},
    )


def set_password(request: HttpRequest, uidb64: str, token: str) -> HttpResponse:
    user = None
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.filter(pk=uid).first()
    except Exception:
        user = None

    if not user or not default_token_generator.check_token(user, token):
        logger.info("SET_PASSWORD invalid uidb64=%s", uidb64)
        return render(request, "app_users/password_set.html", {"invalid": True})

    form = ResetPasswordForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user.set_password(form.cleaned_data["password1"])
        user.is_active = True
        user.save(update_fields=["password", "is_active"])
        logger.info("SET_PASSWORD done email=%s active=%s", user.email, user.is_active)
        return redirect("/")

    return render(request, "app_users/password_set.html", {"form": form, "invalid": False})
