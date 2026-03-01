# FILE: web/app_panel_client/urls.py

from django.urls import path

from .views import buyer_data, contract_application, contract_sign, contracts_list


urlpatterns = [
    path("", contracts_list, name="panel_client_home"),
    path("contracts/", contracts_list, name="panel_client_contracts_list"),
    path("buyer-data/", buyer_data, name="panel_client_buyer_data"),
    path("contract-application/", contract_application, name="panel_client_contract_application"),
    path("contract-sign/", contract_sign, name="panel_client_contract_sign"),
]
