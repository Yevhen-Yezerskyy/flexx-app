# FILE: web/app_panel_client/urls.py  (новое — 2026-02-13)
# PURPOSE: URL панели Client.

from django.urls import path
from .views import index

urlpatterns = [
    path("", index, name="panel_client_index"),
]
