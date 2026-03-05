# FILE: web/app_panel_tippgeber/urls.py  (обновлено — 2026-02-15)
# PURPOSE: Tippgeber: "/" = Meine Kunden (по умолчанию), "/add-client/" = форма добавления клиента.

from django.urls import path

from .views.contracts import contract_preview, contracts_required, contracts_required_sign
from .views.my_clients import my_clients
from .views.send_client import send_client, send_client_status

urlpatterns = [
    path("", my_clients, name="panel_tippgeber_my_clients"),
    path("contracts/required/", contracts_required, name="panel_tippgeber_contracts_required"),
    path("contracts/required/sign/", contracts_required_sign, name="panel_tippgeber_contracts_required_sign"),
    path("contracts/required/preview/<int:issue_id>/", contract_preview, name="panel_tippgeber_contract_preview"),
    path("add-client/", send_client, name="panel_tippgeber_send_client"),
    path("add-client/status/", send_client_status, name="panel_tippgeber_send_client_status"),
]
