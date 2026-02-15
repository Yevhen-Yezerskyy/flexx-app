# FILE: web/app_panel_tippgeber/urls.py  (обновлено — 2026-02-15)
# PURPOSE: Tippgeber: "/" = Meine Kunden (по умолчанию), "/add-client/" = форма добавления клиента.

from django.urls import path

from .views.my_clients import my_clients
from .views.send_client import send_client

urlpatterns = [
    path("", my_clients, name="panel_tippgeber_my_clients"),
    path("add-client/", send_client, name="panel_tippgeber_send_client"),
]
