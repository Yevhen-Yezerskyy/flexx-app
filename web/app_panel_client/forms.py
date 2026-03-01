from __future__ import annotations

from django import forms

from app_panel_admin.forms import _DATE_WIDGET_ADMIN, _normalize_date_like
from app_users.models import FlexxUser
from app_users.age_validation import apply_birth_date_constraints, validate_adult_birth_date


class ClientBuyerDataForm(forms.ModelForm):
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
            "bank_depo_account_holder",
            "bank_depo_depotnummer",
            "bank_depo_name",
            "bank_depo_blz",
            "bank_account_holder",
            "bank_iban",
            "bank_name",
            "bank_bic",
        ]
        widgets = {"birth_date": _DATE_WIDGET_ADMIN}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.is_bound:
            data = self.data.copy()
            data["birth_date"] = _normalize_date_like(data.get("birth_date"))
            self.data = data

        labels = {
            "email": "E-Mail",
            "last_name": "Nachname",
            "first_name": "Vorname",
            "birth_date": "Geburtsdatum",
            "company": "Firma",
            "street": "Straße, Hausnummer",
            "zip_code": "PLZ",
            "city": "Ort",
            "phone": "Telefon",
            "mobile_phone": "Mobiltelefon",
            "fax": "Fax",
            "handelsregister": "Handelsregister",
            "handelsregister_number": "Handelsregister-Nummer",
            "contact_person": "Ansprechpartner",
            "bank_depo_account_holder": "Depotinhaber (Vorname und Nachname oder Firma)",
            "bank_depo_depotnummer": "Depotnummer",
            "bank_depo_name": "Bank / Kreditinstitut",
            "bank_depo_blz": "BLZ",
            "bank_account_holder": "Kontoinhaber (Vorname und Nachname oder Firma)",
            "bank_iban": "IBAN / Kontonummer",
            "bank_name": "Bank / Kreditinstitut",
            "bank_bic": "BIC / BLZ",
        }
        required_fields = {
            "email",
            "last_name",
            "first_name",
            "birth_date",
            "street",
            "zip_code",
            "city",
            "phone",
            "bank_depo_account_holder",
            "bank_depo_depotnummer",
            "bank_depo_name",
            "bank_depo_blz",
            "bank_account_holder",
            "bank_iban",
            "bank_name",
        }

        for field_name, label in labels.items():
            self.fields[field_name].label = label
            self.fields[field_name].required = field_name in required_fields
            self.fields[field_name].error_messages["required"] = f"Bitte geben Sie {label} an."

        self.fields["email"].error_messages["invalid"] = "Bitte geben Sie eine gültige E-Mail-Adresse ein."

        for field_name in (
            "company",
            "mobile_phone",
            "fax",
            "handelsregister",
            "handelsregister_number",
            "contact_person",
            "bank_bic",
        ):
            self.fields[field_name].required = False

        self.fields["birth_date"].input_formats = ["%Y-%m-%d", "%d.%m.%Y"]
        self.fields["birth_date"].widget.attrs["placeholder"] = "Geburtsdatum*"
        apply_birth_date_constraints(self.fields["birth_date"], required=True)

        for field_name, label in labels.items():
            widget = self.fields[field_name].widget
            if isinstance(widget, forms.TextInput | forms.EmailInput):
                suffix = "*" if field_name in required_fields else ""
                widget.attrs["placeholder"] = f"{label}{suffix}"

    def clean_email(self):
        return (self.cleaned_data.get("email") or "").strip().lower()

    def clean_birth_date(self):
        birth_date = self.cleaned_data.get("birth_date")
        validate_adult_birth_date(birth_date)
        return birth_date

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
