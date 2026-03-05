from __future__ import annotations

from django.contrib import admin
from django import forms

from .models import (
    BondIssue,
    BondIssueAttachment,
    BondIssueSystemDocumentSend,
    Contract,
    EmailTemplate,
    FlexxlagerSignature,
    TippgeberContract,
    TippgeberContractText,
)


@admin.register(BondIssue)
class BondIssueAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "title",
        "issue_date",
        "isin_wkn",
        "interest_rate",
        "rate_tippgeber",
        "bond_price",
        "issue_volume",
        "term_months",
        "minimal_bonds_quantity",
        "documents_sent_other",
        "active",
    )
    list_filter = ("active", "issue_date")
    search_fields = ("title", "isin_wkn")
    ordering = ("-issue_date", "-id")


@admin.register(BondIssueAttachment)
class BondIssueAttachmentAdmin(admin.ModelAdmin):
    list_display = ("id", "issue", "description", "filename")
    search_fields = ("issue__title", "description", "file")
    autocomplete_fields = ("issue",)


@admin.register(BondIssueSystemDocumentSend)
class BondIssueSystemDocumentSendAdmin(admin.ModelAdmin):
    list_display = ("id", "issue", "client", "sent_at")
    list_filter = ("sent_at", "issue")
    search_fields = (
        "issue__title",
        "client__email",
        "client__first_name",
        "client__last_name",
    )
    autocomplete_fields = ("issue", "client")
    ordering = ("-sent_at", "-id")


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


@admin.register(TippgeberContract)
class TippgeberContractAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "tippgeber",
        "issue",
        "signed_at",
        "signature_file",
        "signed_contract_pdf",
    )
    list_filter = ("signed_at", "issue")
    search_fields = (
        "tippgeber__email",
        "tippgeber__first_name",
        "tippgeber__last_name",
        "issue__title",
    )
    autocomplete_fields = ("tippgeber", "issue")
    ordering = ("-signed_at", "-id")


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


class TippgeberContractTextAdminForm(forms.ModelForm):
    class Meta:
        model = TippgeberContractText
        fields = ("text",)
        widgets = {
            "text": forms.Textarea(
                attrs={
                    "rows": 30,
                    "style": "width: 98%; min-height: 520px; font-family: ui-monospace, Menlo, monospace;",
                }
            )
        }


@admin.register(TippgeberContractText)
class TippgeberContractTextAdmin(admin.ModelAdmin):
    form = TippgeberContractTextAdminForm
    list_display = ("id",)
    actions = None

    def has_add_permission(self, request):
        if TippgeberContractText.objects.exists():
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
