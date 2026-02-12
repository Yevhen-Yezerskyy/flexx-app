# FILE: web/app_users/admin.py  (новое — 2026-02-12)
# PURPOSE: Простая регистрация модели FlexxUser в admin-site без кастомных форм.

from django.contrib import admin
from .models import FlexxUser


@admin.register(FlexxUser)
class FlexxUserAdmin(admin.ModelAdmin):
    list_display = ("email", "role", "first_name", "last_name", "company", "is_active")
    list_filter = ("role", "is_active")
    search_fields = ("email", "first_name", "last_name", "company")
    ordering = ("email",)
