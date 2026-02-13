# FILE: web/flexx/urls.py  (обновлено — 2026-02-13)
# PURPOSE: Role-based панели + глобальный logout с редиректом на "/"

from django.urls import include, path
from django.contrib.auth import views as auth_views


urlpatterns = [
    path(
        "logout/",
        auth_views.LogoutView.as_view(next_page="/"),
        name="logout",
    ),

    path("", include("app_users.urls")),

    path("panel/client/", include("app_panel_client.urls")),
    path("panel/admin/", include("app_panel_admin.urls")),
    path("panel/tippgeber/", include("app_panel_tippgeber.urls")),
]
