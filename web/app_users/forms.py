# FILE: web/app_users/forms.py  (обновлено — 2026-02-13)
# PURPOSE: Порядок полей: email → password1 → password2 → consent → last_name → first_name.

from __future__ import annotations

from django import forms
from django.core.exceptions import ValidationError

from .models import FlexxUser


class _BaseRegistrationForm(forms.Form):
    email = forms.EmailField(label="E-Mail", max_length=254)

    password1 = forms.CharField(label="Passwort", widget=forms.PasswordInput)
    password2 = forms.CharField(label="Passwort bestätigen", widget=forms.PasswordInput)

    consent = forms.BooleanField(
        label="Ich stimme der Verarbeitung meiner personenbezogenen Daten zu.",
        required=True,
    )

    last_name = forms.CharField(label="Nachname", max_length=150)
    first_name = forms.CharField(label="Vorname", max_length=150)

    role_value: str = ""

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        if FlexxUser.objects.filter(email=email).exists():
            raise ValidationError("Diese E-Mail ist bereits registriert.")
        return email

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get("password1") or ""
        p2 = cleaned.get("password2") or ""
        if p1 != p2:
            self.add_error("password2", "Passwörter stimmen nicht überein.")
        return cleaned

    def save(self) -> FlexxUser:
        user = FlexxUser.objects.create_user(
            email=self.cleaned_data["email"],
            password=self.cleaned_data["password1"],
            first_name=self.cleaned_data["first_name"],
            last_name=self.cleaned_data["last_name"],
            role=self.role_value,
            is_active=False,
        )
        return user


class ClientRegistrationForm(_BaseRegistrationForm):
    role_value = FlexxUser.Role.CLIENT


class AgentRegistrationForm(_BaseRegistrationForm):
    role_value = FlexxUser.Role.AGENT
