# FILE: web/app_users/urls.py  (обновлено — 2026-02-13)
# PURPOSE: Добавлены страницы: forgot password и reset password по ссылке.

from django.urls import path

from .views import (
    home,
    register_client,
    register_agent,
    forgot_password,
    reset_password,
)

urlpatterns = [
    path("", home, name="home"),
    path("reg/client/", register_client, name="reg_client"),
    path("reg/tippgeber/", register_agent, name="reg_tippgeber"),
    path("password/forgot/", forgot_password, name="password_forgot"),
    path("password/reset/<uidb64>/<token>/", reset_password, name="password_reset"),
]
