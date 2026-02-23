from __future__ import annotations

from django.contrib import admin

from .models import BondIssue, BondIssueAttachment, Contract, EmailTemplate


@admin.register(BondIssue)
class BondIssueAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "title",
        "issue_date",
        "interest_rate",
        "bond_price",
        "issue_volume",
        "term_months",
        "minimal_bonds_quantity",
        "active",
    )
    list_filter = ("active", "issue_date")
    search_fields = ("title",)
    ordering = ("-issue_date", "-id")


@admin.register(BondIssueAttachment)
class BondIssueAttachmentAdmin(admin.ModelAdmin):
    list_display = ("id", "issue", "description", "filename")
    search_fields = ("issue__title", "description", "file")
    autocomplete_fields = ("issue",)


@admin.register(Contract)
class ContractAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "client",
        "issue",
        "contract_date",
        "settlement_date",
        "bonds_quantity",
        "nominal_amount",
        "nominal_amount_plus_percent",
        "signed_received_at",
        "paid_at",
    )
    list_filter = ("contract_date", "signed_received_at", "paid_at", "issue")
    search_fields = (
        "client__email",
        "client__first_name",
        "client__last_name",
        "issue__title",
    )
    autocomplete_fields = ("client", "issue")
    ordering = ("-contract_date", "-id")


@admin.register(EmailTemplate)
class EmailTemplateAdmin(admin.ModelAdmin):
    list_display = ("id", "key", "from_role", "to_role", "subject", "is_active", "updated_at")
    list_filter = ("from_role", "to_role", "is_active")
    search_fields = ("key", "subject", "body_text", "placeholder")
    ordering = ("key",)
