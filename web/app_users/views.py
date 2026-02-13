# FILE: web/app_users/views.py  (обновлено — 2026-02-13)
# PURPOSE: Регистрация шлёт 2 письма (юзеру + нам). Добавлены forgot/reset password (2 страницы).


import logging

from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.utils.http import urlsafe_base64_encode

from .forms import ForgotPasswordForm, ResetPasswordForm
from flexx.emailer import send_password_reset_email

logger = logging.getLogger("app_users")
User = get_user_model()


def home(request: HttpRequest) -> HttpResponse:
    return render(request, "app_users/login.html")


def register_client(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = ClientRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            send_registration_pending_email(
                to_email=user.email, role=user.role, first_name=user.first_name, last_name=user.last_name
            )
            send_registration_notify_email(
                role=user.role, user_email=user.email, first_name=user.first_name, last_name=user.last_name
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
            send_registration_pending_email(
                to_email=user.email, role=user.role, first_name=user.first_name, last_name=user.last_name
            )
            send_registration_notify_email(
                role=user.role, user_email=user.email, first_name=user.first_name, last_name=user.last_name
            )
            return render(request, "app_users/register_done.html", {"role": "tippgeber"})
    else:
        form = AgentRegistrationForm()
    return render(request, "app_users/register_agent.html", {"form": form})



def forgot_password(request: HttpRequest) -> HttpResponse:
    sent = False

    if request.method == "POST":
        logger.info(
                "FORGOT_PASSWORD MODEL=%s TABLE=%s DB_NAME=%s",
                User._meta.label,
                User._meta.db_table,
                #settings.DATABASES["default"]["NAME"],
            )        
        form = ForgotPasswordForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data["email"]

            # --- DIAGNOSTIC LOG ---
            logger.info(
                "FORGOT_PASSWORD MODEL=%s TABLE=%s DB_NAME=%s",
                User._meta.label,
                User._meta.db_table,
                #settings.DATABASES["default"]["NAME"],
            )

            user = User.objects.filter(email__iexact=email).first()
            logger.info(
                "FORGOT_PASSWORD lookup email=%s found=%s",
                email,
                bool(user),
            )

            if user:
                uidb64 = urlsafe_base64_encode(str(user.pk).encode("utf-8"))
                token = default_token_generator.make_token(user)
                reset_url = request.build_absolute_uri(
                    f"/password/reset/{uidb64}/{token}/"
                )

                send_password_reset_email(
                    to_email=user.email,
                    first_name=getattr(user, "first_name", ""),
                    last_name=getattr(user, "last_name", ""),
                    reset_url=reset_url,
                )

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
        return render(request, "app_users/password_reset.html", {"valid": False})

    if request.method == "POST":
        form = ResetPasswordForm(request.POST)
        if form.is_valid():
            user.set_password(form.cleaned_data["password1"])
            user.save(update_fields=["password"])
            done = True
    else:
        form = ResetPasswordForm()

    return render(
        request,
        "app_users/password_reset.html",
        {"valid": True, "form": form, "done": done, "email": getattr(user, "email", "")},
    )
