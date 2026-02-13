# FILE: web/app_panel_tippgeber/urls.py  (новое — 2026-02-13)
# PURPOSE: URL панели Tippgeber (agent).

from django.urls import path
from .views import index

urlpatterns = [
    path("", index, name="panel_tippgeber_index"),
]
