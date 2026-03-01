from __future__ import annotations

from django.contrib import admin

from .models import (
    BondIssue,
    BondIssueAttachment,
    Contract,
    DatenschutzeinwilligungText,
    EmailTemplate,
    FlexxlagerSignature,
)


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
        "settlement_date",
        "bonds_quantity",
        "nominal_amount",
        "nominal_amount_plus_percent",
        "signature",
        "contract_pdf",
        "contract_pdf_signed",
        "signed_received_at",
        "paid_at",
    )
    list_filter = ("signed_received_at", "paid_at", "issue")
    search_fields = (
        "client__email",
        "client__first_name",
        "client__last_name",
        "issue__title",
    )
    autocomplete_fields = ("client", "issue")
    ordering = ("-id",)


@admin.register(FlexxlagerSignature)
class FlexxlagerSignatureAdmin(admin.ModelAdmin):
    list_display = ("id", "signature")
    actions = None

    def has_add_permission(self, request):
        if FlexxlagerSignature.objects.exists():
            return False
        return super().has_add_permission(request)

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(DatenschutzeinwilligungText)
class DatenschutzeinwilligungTextAdmin(admin.ModelAdmin):
    list_display = ("id",)
    actions = None

    def has_add_permission(self, request):
        if DatenschutzeinwilligungText.objects.exists():
            return False
        return super().has_add_permission(request)

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(EmailTemplate)
class EmailTemplateAdmin(admin.ModelAdmin):
    list_display = ("key", "from_role", "to_role", "from_text", "subject")
    list_display_links = ("key",)
    list_filter = ("from_role", "to_role", "is_active")
    search_fields = ("key", "from_text", "subject", "body_text")
    ordering = ("from_role", "key")
    actions = None

    def get_form(self, request, obj=None, change=False, **kwargs):
        form = super().get_form(request, obj, change=change, **kwargs)
        if "subject" in form.base_fields:
            form.base_fields["subject"].widget.attrs["style"] = "width: 36em;"
        return form

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return ("key", "placeholder")
        return ()
