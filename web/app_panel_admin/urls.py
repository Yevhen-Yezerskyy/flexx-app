# FILE: web/app_panel_admin/urls.py  (новое — 2026-02-13)
# PURPOSE: URL панели Admin.

from django.urls import path
from .views import index

urlpatterns = [
    path("", index, name="panel_admin_index"),
]
