# FILE: web/app_panel_admin/forms.py  (обновлено — 2026-02-15)
# PURPOSE: Добавлен AdminTippgeberForm для редактирования Tippgeber в админке.

from __future__ import annotations

from typing import Dict

from django import forms

from flexx.contract_fields import CONTRACT_FIELDS
from flexx.models import BondIssue

from app_users.models import FlexxUser, TippgeberClient


class BondIssueForm(forms.ModelForm):
    class Meta:
        model = BondIssue
        fields = [
            "active",
            "title",
            "issue_date",
            "interest_rate",
            "bond_price",
            "issue_volume",
            "term_months",
        ]
        widgets = {"issue_date": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["active"].label = "Aktiv"
        self.fields["title"].label = "Name der Emission"
        self.fields["issue_date"].label = "Emissionsdatum"
        self.fields["interest_rate"].label = "Zinssatz (%)"
        self.fields["bond_price"].label = "Preis je Anleihe (€)"
        self.fields["issue_volume"].label = "Emissionsvolumen (€)"
        self.fields["term_months"].label = "Laufzeit (Monate)"

        contract: Dict[str, str] = {}
        if self.instance and isinstance(self.instance.contract, dict):
            contract = self.instance.contract

        for f in CONTRACT_FIELDS:
            key = f["key"]
            self.fields[f"contract__{key}"] = forms.CharField(
                required=False,
                label=f["label_de"],
                widget=forms.Textarea(attrs={"rows": f["rows"]}),
                initial=contract.get(key, ""),
            )

    def clean(self):
        cleaned = super().clean()
        out: Dict[str, str] = {}
        for f in CONTRACT_FIELDS:
            key = f["key"]
            val = cleaned.get(f"contract__{key}", "")
            out[key] = "" if val is None else str(val)
        cleaned["contract"] = out
        return cleaned

    def save(self, commit=True):
        obj: BondIssue = super().save(commit=False)
        obj.contract = self.cleaned_data.get("contract", {}) or {}
        if commit:
            obj.save()
        return obj


_DATE_WIDGET_ADMIN = forms.DateInput(
    format="%Y-%m-%d",
    attrs={
        "type": "date",
        "class": "border border-[var(--text)] rounded-md px-4 py-2 focus:outline-none",
    },
)


class AdminClientForm(forms.ModelForm):
    """Admin create/edit Client (FlexxUser role=client) + link to Tippgeber via TippgeberClient."""

    tippgeber_id = forms.ChoiceField(required=False)

    class Meta:
        model = FlexxUser
        fields = [
            "email",
            "last_name",
            "first_name",
            "birth_date",
            "company",
            "street",
            "zip_code",
            "city",
            "phone",
            "fax",
            "handelsregister",
            "handelsregister_number",
            "contact_person",
            "bank_depo_account_holder",
            "bank_depo_iban",
            "bank_depo_name",
            "bank_depo_bic",
            "bank_account_holder",
            "bank_iban",
            "bank_name",
            "bank_bic",
            "is_active",
        ]
        widgets = {
            "birth_date": _DATE_WIDGET_ADMIN,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["is_active"].label = "Aktiv"

        for f in ("email", "last_name", "first_name", "street", "zip_code", "city", "phone"):
            self.fields[f].required = True

        for f in (
            "bank_depo_account_holder",
            "bank_depo_iban",
            "bank_depo_name",
            "bank_depo_bic",
            "bank_account_holder",
            "bank_iban",
            "bank_name",
            "bank_bic",
        ):
            self.fields[f].required = False

        self.fields["birth_date"].required = False
        self.fields["fax"].required = False
        self.fields["company"].required = False
        self.fields["contact_person"].required = False
        self.fields["handelsregister"].required = False
        self.fields["handelsregister_number"].required = False

        if "birth_date" in self.fields:
            self.fields["birth_date"].input_formats = ["%Y-%m-%d", "%d.%m.%Y"]

        tips = FlexxUser.objects.filter(role=FlexxUser.Role.AGENT).order_by("email")
        choices = [("", "—")]
        for u in tips:
            label = f"{u.email} — {u.first_name} {u.last_name}".strip()
            choices.append((str(u.id), label))
        self.fields["tippgeber_id"].choices = choices
        self.fields["tippgeber_id"].label = "Tippgeber"

        if self.instance and self.instance.pk:
            link = TippgeberClient.objects.filter(client=self.instance).select_related("tippgeber").first()
            if link and link.tippgeber_id:
                self.initial["tippgeber_id"] = str(link.tippgeber_id)

    def clean_email(self):
        return (self.cleaned_data.get("email") or "").strip().lower()

    def clean(self):
        cleaned = super().clean()

        company = (cleaned.get("company") or "").strip()
        hr = (cleaned.get("handelsregister") or "").strip()
        hrn = (cleaned.get("handelsregister_number") or "").strip()
        if company:
            if not hr:
                self.add_error("handelsregister", "Pflichtfeld, wenn Firma gesetzt ist.")
            if not hrn:
                self.add_error("handelsregister_number", "Pflichtfeld, wenn Firma gesetzt ist.")

        email = (cleaned.get("email") or "").strip().lower()
        if email:
            qs = FlexxUser.objects.filter(email=email)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                self.add_error("email", "Diese E-Mail ist bereits vergeben.")

        return cleaned


class AdminTippgeberForm(forms.ModelForm):
    """Admin edit Tippgeber (FlexxUser role=agent)."""

    class Meta:
        model = FlexxUser
        fields = [
            "email",
            "last_name",
            "first_name",
            "phone",
            "is_active",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["is_active"].label = "Aktiv"
        for f in ("email", "last_name", "first_name"):
            self.fields[f].required = True
        self.fields["phone"].required = False

    def clean_email(self):
        return (self.cleaned_data.get("email") or "").strip().lower()

    def clean(self):
        cleaned = super().clean()
        email = (cleaned.get("email") or "").strip().lower()
        if email:
            qs = FlexxUser.objects.filter(email=email)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                self.add_error("email", "Diese E-Mail ist bereits vergeben.")
        return cleaned
