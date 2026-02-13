# FILE: web/app_users/admin.py  (обновлено — 2026-02-13)
# PURPOSE: Админка FlexxUser без Django Permissions (groups/user_permissions/is_superuser убраны).

from __future__ import annotations

from django.contrib import admin
from .models import FlexxUser


@admin.register(FlexxUser)
class FlexxUserAdmin(admin.ModelAdmin):
    list_display = (
        "email",
        "role",
        "is_active",
        "first_name",
        "last_name",
        "company",
    )
    list_filter = ("role", "is_active")
    search_fields = ("email", "first_name", "last_name", "company")
    ordering = ("email",)
    readonly_fields = ("date_joined", "last_login")

    exclude = (
        "groups",
        "user_permissions",
        "is_superuser",
    )

    fieldsets = (
        ("Account", {"fields": ("email", "role", "is_active")}),
        ("Person", {"fields": ("first_name", "last_name", "birth_date")}),
        ("Company", {"fields": ("company",)}),
        ("Meta", {"fields": ("date_joined", "last_login")}),
    )
