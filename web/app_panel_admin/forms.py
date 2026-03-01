# FILE: web/app_panel_admin/forms.py  (обновлено — 2026-02-16)
# PURPOSE: Emission-Form: добавить поле minimal_bonds_quantity (минимальное количество облигаций) + сохранить прежние фиксы даты/десятичных/contract__.

from __future__ import annotations

from typing import Dict

from django import forms

from app_users.age_validation import apply_birth_date_constraints, validate_adult_birth_date
from app_users.models import FlexxUser, TippgeberClient
from flexx.contract_fields import CONTRACT_FIELDS
from flexx.models import BondIssue


def _normalize_decimal_like(v) -> str:
    s = "" if v is None else str(v).strip()
    if not s:
        return s
    return s.replace(" ", "").replace(",", ".")


def _normalize_date_like(v) -> str:
    s = "" if v is None else str(v).strip()
    if not s:
        return s
    # allow DD.MM.YYYY -> YYYY-MM-DD
    if len(s) == 10 and s[2] == "." and s[5] == ".":
        dd, mm, yyyy = s[0:2], s[3:5], s[6:10]
        if dd.isdigit() and mm.isdigit() and yyyy.isdigit():
            return f"{yyyy}-{mm}-{dd}"
    return s


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
            "minimal_bonds_quantity",
        ]
        widgets = {"issue_date": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # normalize POST BEFORE validation (DE запятая + DD.MM.YYYY)
        if self.is_bound:
            d = self.data.copy()
            d["issue_date"] = _normalize_date_like(d.get("issue_date"))
            d["interest_rate"] = _normalize_decimal_like(d.get("interest_rate"))
            d["bond_price"] = _normalize_decimal_like(d.get("bond_price"))
            d["issue_volume"] = _normalize_decimal_like(d.get("issue_volume"))
            self.data = d

        self.fields["active"].label = "Aktiv"
        self.fields["title"].label = "Name der Emission"
        self.fields["issue_date"].label = "Emissionsdatum"
        self.fields["interest_rate"].label = "Zinssatz (%)"
        self.fields["bond_price"].label = "Preis je Anleihe (€)"
        self.fields["issue_volume"].label = "Volumen (€)"
        self.fields["term_months"].label = "Laufzeit (Monate)"
        self.fields["minimal_bonds_quantity"].label = "Mindestmenge"

        self.fields["issue_date"].input_formats = ["%Y-%m-%d", "%d.%m.%Y"]

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
        "class": "border border-gray-400 rounded-md px-4 py-2 focus:outline-none",
    },
)


class AdminClientForm(forms.ModelForm):
    """Admin create/edit Client (FlexxUser role=client) + link to Tippgeber via TippgeberClient."""

    tippgeber_id = forms.ChoiceField(required=False)
    issue_id = forms.ChoiceField(required=False)

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
            "is_active",
        ]
        widgets = {"birth_date": _DATE_WIDGET_ADMIN}

    def __init__(self, *args, **kwargs):
        require_issue = bool(kwargs.pop("require_issue", False))
        super().__init__(*args, **kwargs)

        if self.is_bound:
            d = self.data.copy()
            d["birth_date"] = _normalize_date_like(d.get("birth_date"))
            self.data = d

        self.fields["is_active"].label = "Aktiv"

        for f in ("email", "last_name", "first_name"):
            self.fields[f].required = True

        self.fields["street"].required = False
        self.fields["zip_code"].required = False
        self.fields["city"].required = False
        self.fields["phone"].required = False
        for f in (
            "bank_depo_account_holder",
            "bank_depo_depotnummer",
            "bank_depo_name",
            "bank_depo_blz",
            "bank_account_holder",
            "bank_iban",
            "bank_name",
            "bank_bic",
        ):
            self.fields[f].required = False

        self.fields["birth_date"].required = False
        self.fields["mobile_phone"].required = False
        self.fields["fax"].required = False
        self.fields["company"].required = False
        self.fields["contact_person"].required = False
        self.fields["handelsregister"].required = False
        self.fields["handelsregister_number"].required = False

        self.fields["birth_date"].input_formats = ["%Y-%m-%d", "%d.%m.%Y"]
        apply_birth_date_constraints(self.fields["birth_date"], required=False)

        tips = FlexxUser.objects.filter(role=FlexxUser.Role.AGENT).order_by("email")
        choices = [("", "—")]
        for u in tips:
            label = f"{u.email} — {u.first_name} {u.last_name}".strip()
            choices.append((str(u.id), label))
        self.fields["tippgeber_id"].choices = choices
        self.fields["tippgeber_id"].label = "Tippgeber"

        issues = BondIssue.objects.filter(active=True).order_by("-issue_date", "-id")
        issue_choices = [("", "—")]
        for issue in issues:
            issue_choices.append((str(issue.id), f"{issue.issue_date:%d.%m.%Y}: {issue.title}"))
        self.fields["issue_id"].choices = issue_choices
        self.fields["issue_id"].label = "Emission"
        self.fields["issue_id"].required = require_issue
        self.fields["issue_id"].error_messages["required"] = "Bitte wählen Sie eine Emission aus."

        if self.instance and self.instance.pk:
            link = TippgeberClient.objects.filter(client=self.instance).select_related("tippgeber").first()
            if link and link.tippgeber_id:
                self.initial["tippgeber_id"] = str(link.tippgeber_id)

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

        issue_id_raw = (cleaned.get("issue_id") or "").strip()
        if issue_id_raw:
            try:
                issue_id = int(issue_id_raw)
            except Exception:
                self.add_error("issue_id", "Bitte wählen Sie eine Emission aus.")
            else:
                issue = BondIssue.objects.filter(id=issue_id, active=True).first()
                if not issue:
                    self.add_error("issue_id", "Bitte wählen Sie eine Emission aus.")
                else:
                    cleaned["issue"] = issue

        return cleaned


class AdminTippgeberForm(forms.ModelForm):
    """Admin edit Tippgeber (FlexxUser role=agent)."""

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
            "is_active",
        ]
        widgets = {"birth_date": _DATE_WIDGET_ADMIN}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.is_bound:
            d = self.data.copy()
            d["birth_date"] = _normalize_date_like(d.get("birth_date"))
            self.data = d

        self.fields["is_active"].label = "Aktiv"
        self.fields["birth_date"].required = False
        self.fields["mobile_phone"].required = False
        self.fields["fax"].required = False
        self.fields["company"].required = False
        self.fields["contact_person"].required = False
        self.fields["handelsregister"].required = False
        self.fields["handelsregister_number"].required = False
        self.fields["bank_account_holder"].required = False
        self.fields["bank_iban"].required = False
        self.fields["bank_name"].required = False
        self.fields["bank_bic"].required = False
        self.fields["birth_date"].input_formats = ["%Y-%m-%d", "%d.%m.%Y"]
        apply_birth_date_constraints(self.fields["birth_date"], required=False)

        for f in ("email", "last_name", "first_name", "street", "zip_code", "city", "phone"):
            self.fields[f].required = True

    def clean_email(self):
        return (self.cleaned_data.get("email") or "").strip().lower()

    def clean_birth_date(self):
        birth_date = self.cleaned_data.get("birth_date")
        validate_adult_birth_date(birth_date)
        return birth_date
