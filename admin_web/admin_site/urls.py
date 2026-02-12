# FILE: admin_web/admin_site/urls.py  (обновлено — 2026-02-12)
# PURPOSE: На корне админ-сайта сделать редирект на /admin/, сама админка остаётся на /admin/.

from django.contrib import admin
from django.urls import path
from django.views.generic import RedirectView

urlpatterns = [
    path("", RedirectView.as_view(url="/admin/", permanent=False)),
    path("admin/", admin.site.urls),
]