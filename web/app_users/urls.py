# FILE: web/app_users/urls.py  (обновлено — 2026-02-13)
# PURPOSE: /reg/tippgeber вместо /reg/agent.

from django.urls import path
from .views import home, register_client, register_agent

urlpatterns = [
    path("", home, name="home"),
    path("reg/client/", register_client, name="reg_client"),
    path("reg/tippgeber/", register_agent, name="reg_tippgeber"),
]