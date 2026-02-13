# FILE: web/app_users/views.py  (обновлено — 2026-02-13)
# PURPOSE: Действия логируются (регистрация + какие письма кому; reset-request; reset/set password done/invalid).
#          Одноразовые ссылки: default_token_generator становится невалидным после смены user.password; TTL = 7 дней (settings).

from __future__ import annotations

import logging

from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
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
)

logger = logging.getLogger(__name__)
User = get_user_model()


def _build_user_link(request: HttpRequest, *, view_name: str, user, token: str) -> str:
    uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
    path = reverse(view_name, kwargs={"uidb64": uidb64, "token": token})
    return request.build_absolute_uri(path)


def home(request: HttpRequest) -> HttpResponse:
    return render(request, "app_users/login.html")


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
                "REGISTER_OK role=%s email=%s mail_user_ok=%s mail_notify_ok=%s",
                user.role,
                user.email,
                mail_user_ok,
                mail_notify_ok,
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
                "REGISTER_OK role=%s email=%s mail_user_ok=%s mail_notify_ok=%s",
                user.role,
                user.email,
                mail_user_ok,
                mail_notify_ok,
            )
            return render(request, "app_users/register_done.html", {"role": "tippgeber"})
    else:
        form = AgentRegistrationForm()
    return render(request, "app_users/register_agent.html", {"form": form})


def forgot_password(request: HttpRequest) -> HttpResponse:
    sent = False

    if request.method == "POST":
        form = ForgotPasswordForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data["email"]
            user = User.objects.filter(email__iexact=email).first()
            found = bool(user)

            mail_ok = None
            if user:
                token = default_token_generator.make_token(user)
                reset_url = _build_user_link(request, view_name="password_reset", user=user, token=token)

                mail_ok = send_password_reset_email(
                    to_email=user.email,
                    first_name=getattr(user, "first_name", ""),
                    last_name=getattr(user, "last_name", ""),
                    reset_url=reset_url,
                )

            logger.info("PASSWORD_RESET_REQUEST email=%s found=%s mail_ok=%s", email, found, mail_ok)
            sent = True
    else:
        form = ForgotPasswordForm()

    return render(request, "app_users/password_forgot.html", {"form": form, "sent": sent})


def reset_password(request: HttpRequest, uidb64: str, token: str) -> HttpResponse:
    user = None
    valid = False
    done = False

    try:
        pk = int(force_str(urlsafe_base64_decode(uidb64)))
        user = User.objects.get(pk=pk)
        valid = default_token_generator.check_token(user, token)
    except Exception:
        user = None
        valid = False

    if not valid or not user:
        logger.info("PASSWORD_RESET_INVALID uidb64=%s", uidb64)
        return render(request, "app_users/password_reset.html", {"valid": False})

    if request.method == "POST":
        form = ResetPasswordForm(request.POST)
        if form.is_valid():
            user.set_password(form.cleaned_data["password1"])
            user.save(update_fields=["password"])
            done = True
            logger.info("PASSWORD_RESET_DONE email=%s", getattr(user, "email", ""))
    else:
        form = ResetPasswordForm()

    return render(
        request,
        "app_users/password_reset.html",
        {"valid": True, "form": form, "done": done, "email": getattr(user, "email", "")},
    )


def set_password(request: HttpRequest, uidb64: str, token: str) -> HttpResponse:
    user = None
    valid = False
    done = False

    try:
        pk = int(force_str(urlsafe_base64_decode(uidb64)))
        user = User.objects.get(pk=pk)
        valid = default_token_generator.check_token(user, token)
    except Exception:
        user = None
        valid = False

    if not valid or not user:
        logger.info("PASSWORD_SET_INVALID uidb64=%s", uidb64)
        return render(request, "app_users/password_reset.html", {"valid": False})

    if request.method == "POST":
        form = ResetPasswordForm(request.POST)
        if form.is_valid():
            user.set_password(form.cleaned_data["password1"])
            user.save(update_fields=["password"])
            done = True
            logger.info("PASSWORD_SET_DONE email=%s", getattr(user, "email", ""))
    else:
        form = ResetPasswordForm()

    return render(
        request,
        "app_users/password_reset.html",
        {"valid": True, "form": form, "done": done, "email": getattr(user, "email", "")},
    )
