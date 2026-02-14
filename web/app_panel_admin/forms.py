# FILE: web/app_panel_admin/forms.py  (новое — 2026-02-14)
# PURPOSE: Form для BondIssue + редактирование contract JSON по справочнику flexx/contract_fields.py.

from __future__ import annotations

from typing import Dict

from django import forms

from flexx.contract_fields import CONTRACT_FIELDS
from flexx.models import BondIssue


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
