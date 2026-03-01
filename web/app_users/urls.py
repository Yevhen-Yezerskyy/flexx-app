# FILE: web/app_users/urls.py  (обновлено — 2026-02-16)
# PURPOSE: Public endpoint для Stückzinstabelle по эмиссии (для переиспользуемого попапа в админке/панелях).

from django.urls import path

from .views import (
    datenschutz,
    home,
    impressum,
    register_agent,
    forgot_password,
    set_password,
    public_issue_interest_table,
)

urlpatterns = [
    path("", home, name="home"),
    path("reg/tippgeber/", register_agent, name="reg_tippgeber"),
    path("impressum/", impressum, name="impressum"),
    path("datenschutz/", datenschutz, name="datenschutz"),
    path("password/forgot/", forgot_password, name="password_forgot"),
    path("password/set/<uidb64>/<token>/", set_password, name="password_set"),
    path("issue/<int:issue_id>/interest-table/", public_issue_interest_table, name="public_issue_interest_table"),
]
