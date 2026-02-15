# FILE: web/app_panel_tippgeber/forms.py  (обновлено — 2026-02-15)
# PURPOSE: Даты рождения не “слетают” при ошибках формы: рендерим date-поля через widget (он держит bound-значение), и задаём ему нужные attrs (type=date + class).

from __future__ import annotations

from django import forms

from app_users.models import FlexxUser


_DATE_WIDGET = forms.DateInput(
    format="%Y-%m-%d",
    attrs={
        "type": "date",
        "class": "border border-[var(--text)] rounded-md px-4 py-2 focus:outline-none",
    },
)


class TippgeberProfileForm(forms.ModelForm):
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
            "bank_account_holder",
            "bank_iban",
            "bank_name",
            "bank_bic",
        ]
        widgets = {"birth_date": _DATE_WIDGET}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for f in ("email", "last_name", "first_name", "birth_date", "street", "zip_code", "city", "phone"):
            self.fields[f].required = True

        for f in ("bank_account_holder", "bank_iban", "bank_name"):
            self.fields[f].required = True

        self.fields["bank_bic"].required = False
        self.fields["fax"].required = False
        self.fields["company"].required = False
        self.fields["contact_person"].required = False
        self.fields["handelsregister"].required = False
        self.fields["handelsregister_number"].required = False

        if "birth_date" in self.fields:
            self.fields["birth_date"].input_formats = ["%Y-%m-%d", "%d.%m.%Y"]

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
        return cleaned


class ClientCreateForm(forms.ModelForm):
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
        ]
        widgets = {"birth_date": _DATE_WIDGET}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for f in ("email", "last_name", "first_name", "street", "zip_code", "city", "phone"):
            self.fields[f].required = True

        self.fields["birth_date"].required = False
        self.fields["fax"].required = False
        self.fields["company"].required = False
        self.fields["contact_person"].required = False
        self.fields["handelsregister"].required = False
        self.fields["handelsregister_number"].required = False

        if "birth_date" in self.fields:
            self.fields["birth_date"].input_formats = ["%Y-%m-%d", "%d.%m.%Y"]

    def clean_email(self):
        return (self.cleaned_data.get("email") or "").strip().lower()

    def validate_unique(self):
        return

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
        return cleaned


class ConfirmationsForm(forms.Form):
    consent1 = forms.BooleanField(required=True)
    consent2 = forms.BooleanField(required=True)
