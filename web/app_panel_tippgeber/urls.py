# FILE: web/app_panel_tippgeber/urls.py  (обновлено — 2026-02-15)
# PURPOSE: Tippgeber: "/" = Meine Kunden (по умолчанию), "/add-client/" = форма добавления клиента.

from django.urls import path

from .views.issues import issues_list
from .views.my_clients import my_clients
from .views.send_client import send_client, send_client_status

urlpatterns = [
    path("", my_clients, name="panel_tippgeber_my_clients"),
    path("add-client/", send_client, name="panel_tippgeber_send_client"),
    path("add-client/status/", send_client_status, name="panel_tippgeber_send_client_status"),
    path("issues/", issues_list, name="panel_tippgeber_issues_list"),
]
