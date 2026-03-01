# FILE: web/app_panel_tippgeber/forms.py  (обновлено — 2026-02-15)
# PURPOSE: Даты рождения не “слетают” при ошибках формы: рендерим date-поля через widget (он держит bound-значение), и задаём ему нужные attrs (type=date + class).

from __future__ import annotations

from django import forms

from app_users.age_validation import apply_birth_date_constraints, validate_adult_birth_date
from app_users.models import FlexxUser


_DATE_WIDGET = forms.DateInput(
    format="%Y-%m-%d",
    attrs={
        "type": "date",
        "placeholder": "Geburtsdatum*",
        "class": "border border-gray-400 rounded-md px-4 py-2 focus:outline-none bg-white",
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
            "mobile_phone",
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
        self.fields["mobile_phone"].required = False
        self.fields["fax"].required = False
        self.fields["company"].required = False
        self.fields["contact_person"].required = False
        self.fields["handelsregister"].required = False
        self.fields["handelsregister_number"].required = False
        self.fields["birth_date"].input_formats = ["%Y-%m-%d", "%d.%m.%Y"]
        apply_birth_date_constraints(self.fields["birth_date"], required=True)

    def clean_email(self):
        return (self.cleaned_data.get("email") or "").strip().lower()

    def clean_birth_date(self):
        birth_date = self.cleaned_data.get("birth_date")
        validate_adult_birth_date(birth_date)
        return birth_date

    def clean(self):
        return super().clean()


class ClientCreateForm(forms.ModelForm):
    class Meta:
        model = FlexxUser
        fields = [
            "email",
            "last_name",
            "first_name",
            "company",
            "street",
            "zip_code",
            "city",
            "phone",
            "mobile_phone",
            "fax",
            "handelsregister",
            "handelsregister_number",
            "contact_person",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for f in ("email", "last_name", "first_name", "street", "zip_code", "city", "phone"):
            self.fields[f].required = True

        self.fields["mobile_phone"].required = False
        self.fields["fax"].required = False
        self.fields["company"].required = False
        self.fields["contact_person"].required = False
        self.fields["handelsregister"].required = False
        self.fields["handelsregister_number"].required = False

    def clean_email(self):
        return (self.cleaned_data.get("email") or "").strip().lower()

    def validate_unique(self):
        return

    def clean(self):
        return super().clean()


class ConfirmationsForm(forms.Form):
    consent1 = forms.BooleanField(required=True)
    consent2 = forms.BooleanField(required=True)
