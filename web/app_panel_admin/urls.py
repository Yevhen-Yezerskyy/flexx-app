# FILE: web/app_panel_admin/urls.py  (обновлено — 2026-02-15)
# PURPOSE: Admin panel URLs: Kunden + Tippgeber lists/edit/delete + toggle aktiv/inaktiv (optional email notify).

from django.urls import path

from .views.clients import clients_list, clients_create, clients_edit, clients_toggle_active, clients_delete
from .views.issues import issues_list, issues_create, issues_edit, issues_delete
from .views.tippgeber import tippgeber_list, tippgeber_edit, tippgeber_toggle_active, tippgeber_delete

urlpatterns = [
    path("", clients_list, name="panel_admin_clients"),
    path("clients/", clients_list, name="panel_admin_clients_alias"),
    path("clients/new/", clients_create, name="panel_admin_clients_create"),
    path("clients/<int:user_id>/edit/", clients_edit, name="panel_admin_clients_edit"),
    path("clients/<int:user_id>/toggle-active/", clients_toggle_active, name="panel_admin_clients_toggle_active"),
    path("clients/<int:user_id>/delete/", clients_delete, name="panel_admin_clients_delete"),

    path("tippgeber/", tippgeber_list, name="panel_admin_tippgeber_list"),
    path("tippgeber/<int:user_id>/edit/", tippgeber_edit, name="panel_admin_tippgeber_edit"),
    path("tippgeber/<int:user_id>/toggle-active/", tippgeber_toggle_active, name="panel_admin_tippgeber_toggle_active"),
    path("tippgeber/<int:user_id>/delete/", tippgeber_delete, name="panel_admin_tippgeber_delete"),

    path("issues/", issues_list, name="panel_admin_issues_list"),
    path("issues/new/", issues_create, name="panel_admin_issues_create"),
    path("issues/<int:issue_id>/edit/", issues_edit, name="panel_admin_issues_edit"),
    path("issues/<int:issue_id>/delete/", issues_delete, name="panel_admin_issues_delete"),
]
