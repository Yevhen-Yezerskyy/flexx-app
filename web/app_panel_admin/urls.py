# FILE: web/app_panel_admin/urls.py  (обновлено — 2026-02-14)
# PURPOSE: Добавлены URLs Tippgeber list + activate/deactivate.

from django.urls import path

from .views.index import index
from .views.issues import issues_list, issues_create, issues_edit, issues_delete
from .views.tippgeber import tippgeber_list, tippgeber_activate, tippgeber_deactivate

urlpatterns = [
    path("", index, name="panel_admin_index"),

    path("tippgeber/", tippgeber_list, name="panel_admin_tippgeber_list"),
    path("tippgeber/<int:user_id>/activate/", tippgeber_activate, name="panel_admin_tippgeber_activate"),
    path("tippgeber/<int:user_id>/deactivate/", tippgeber_deactivate, name="panel_admin_tippgeber_deactivate"),

    path("issues/", issues_list, name="panel_admin_issues_list"),
    path("issues/new/", issues_create, name="panel_admin_issues_create"),
    path("issues/<int:issue_id>/edit/", issues_edit, name="panel_admin_issues_edit"),
    path("issues/<int:issue_id>/delete/", issues_delete, name="panel_admin_issues_delete"),
]
