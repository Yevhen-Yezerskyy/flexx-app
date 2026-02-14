# FILE: web/app_panel_tippgeber/urls.py  (новое — 2026-02-14)
# PURPOSE: URLs панели Tippgeber: "/" = Kunden senden, + Meine Kunden.

from django.urls import path
from .views.send_client import send_client
from .views.my_clients import my_clients

urlpatterns = [
    path("", send_client, name="panel_tippgeber_send_client"),
    path("my-clients/", my_clients, name="panel_tippgeber_my_clients"),
]