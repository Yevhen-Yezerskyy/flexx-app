from __future__ import annotations

from django import forms

from app_users.models import FlexxUser


def _normalize_date_like(v) -> str:
    s = "" if v is None else str(v).strip()
    if not s:
        return s
    if len(s) == 10 and s[2] == "." and s[5] == ".":
        dd, mm, yyyy = s[0:2], s[3:5], s[6:10]
        if dd.isdigit() and mm.isdigit() and yyyy.isdigit():
            return f"{yyyy}-{mm}-{dd}"
    return s


_DATE_WIDGET = forms.DateInput(
    format="%Y-%m-%d",
    attrs={
        "type": "date",
        "class": "border border-gray-400 rounded-md px-4 py-2 focus:outline-none",
    },
)


class ClientSelfForm(forms.ModelForm):
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
        widgets = {"birth_date": _DATE_WIDGET}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.is_bound:
            d = self.data.copy()
            d["birth_date"] = _normalize_date_like(d.get("birth_date"))
            self.data = d

        for f in (
            "email",
            "last_name",
            "first_name",
            "street",
            "zip_code",
            "city",
            "phone",
            "birth_date",
            "bank_account_holder",
            "bank_iban",
            "bank_name",
            "bank_depo_account_holder",
            "bank_depo_depotnummer",
            "bank_depo_name",
        ):
            self.fields[f].required = True

        self.fields["mobile_phone"].required = False
        self.fields["fax"].required = False
        self.fields["company"].required = False
        self.fields["contact_person"].required = False
        self.fields["handelsregister"].required = False
        self.fields["handelsregister_number"].required = False
        self.fields["bank_depo_blz"].required = False
        self.fields["bank_bic"].required = False

        self.fields["birth_date"].input_formats = ["%Y-%m-%d", "%d.%m.%Y"]

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
