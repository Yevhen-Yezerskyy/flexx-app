# FILE: web/app_users/views.py  (обновлено — 2026-02-13)
# PURPOSE: Текст role для done-страницы: tippgeber.

from django.shortcuts import render
from django.http import HttpRequest, HttpResponse

from .forms import ClientRegistrationForm, AgentRegistrationForm
from flexx.emailer import send_registration_pending_email


def home(request: HttpRequest) -> HttpResponse:
    return render(request, "app_users/login.html")


def register_client(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = ClientRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            send_registration_pending_email(
                to_email=user.email,
                role=user.role,
                first_name=user.first_name,
                last_name=user.last_name,
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
                to_email=user.email,
                role=user.role,
                first_name=user.first_name,
                last_name=user.last_name,
            )
            return render(request, "app_users/register_done.html", {"role": "tippgeber"})
    else:
        form = AgentRegistrationForm()
    return render(request, "app_users/register_agent.html", {"form": form})
