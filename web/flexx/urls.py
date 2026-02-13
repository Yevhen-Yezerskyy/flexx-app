# FILE: web/flexx/urls.py  (обновлено — 2026-02-13)
# PURPOSE: Подключены role-based панели: client/admin/tippgeber (agent) + сохранён app_users на "/".

from django.urls import include, path

urlpatterns = [
    path("", include("app_users.urls")),
    path("panel/client/", include("app_panel_client.urls")),
    path("panel/admin/", include("app_panel_admin.urls")),
    path("panel/tippgeber/", include("app_panel_tippgeber.urls")),
]
