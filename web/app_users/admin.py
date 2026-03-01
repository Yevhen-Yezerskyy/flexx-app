# FILE: web/app_users/admin.py  (обновлено — 2026-02-13)
# PURPOSE: Админка FlexxUser без Django Permissions (groups/user_permissions/is_superuser убраны).

from __future__ import annotations

from django.contrib import admin
from django import forms

from .age_validation import apply_birth_date_constraints, validate_adult_birth_date
from .models import FlexxUser, TippgeberClient


class FlexxUserAdminForm(forms.ModelForm):
    class Meta:
        model = FlexxUser
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "birth_date" in self.fields:
            apply_birth_date_constraints(self.fields["birth_date"], required=False)

    def clean_birth_date(self):
        birth_date = self.cleaned_data.get("birth_date")
        validate_adult_birth_date(birth_date)
        return birth_date


@admin.register(FlexxUser)
class FlexxUserAdmin(admin.ModelAdmin):
    form = FlexxUserAdminForm
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


@admin.register(TippgeberClient)
class TippgeberClientAdmin(admin.ModelAdmin):
    list_display = ("id", "tippgeber", "client", "created_at")
    search_fields = (
        "tippgeber__email",
        "tippgeber__first_name",
        "tippgeber__last_name",
        "client__email",
        "client__first_name",
        "client__last_name",
    )
    autocomplete_fields = ("tippgeber", "client")
    readonly_fields = ("created_at",)
