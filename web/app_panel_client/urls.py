# FILE: web/app_panel_client/urls.py

from django.urls import path
from .views import contract_create, contract_pick_issue, contract_edit, contract_delete, contracts_list, issues_list, index

urlpatterns = [
    path("", contract_create, name="panel_client_contract_create"),
    path("contract/new/", contract_pick_issue, name="panel_client_contract_pick_issue"),
    path("contracts/<int:contract_id>/edit/", contract_edit, name="panel_client_contract_edit"),
    path("contracts/<int:contract_id>/delete/", contract_delete, name="panel_client_contract_delete"),
    path("contracts/", contracts_list, name="panel_client_contracts_list"),
    path("issues/", issues_list, name="panel_client_issues_list"),
    path("index/", index, name="panel_client_index"),
]
