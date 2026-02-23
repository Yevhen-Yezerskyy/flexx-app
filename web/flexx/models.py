# FILE: web/flexx/models.py  (обновлено — 2026-02-16)
# PURPOSE: Добавлено поле minimal_bonds_quantity в BondIssue.
#          Contract содержит settlement_date, bonds_quantity,
#          nominal_amount, nominal_amount_plus_percent.

from __future__ import annotations

import os

from django.db import models
from app_users.models import FlexxUser


def bond_issue_attachment_upload_to(instance: "BondIssueAttachment", filename: str) -> str:
    return f"bond_issues/{instance.issue_id}/{filename}"


def contract_pdf_upload_to(instance: "Contract", filename: str) -> str:
    return f"contracts/{instance.issue_id}/{instance.client_id}/{filename}"


class BondIssue(models.Model):
    title = models.CharField(max_length=255)  # Name der Emission
    issue_date = models.DateField()  # Emissionsdatum

    interest_rate = models.DecimalField(max_digits=5, decimal_places=2)  # Zinssatz (%)
    bond_price = models.DecimalField(max_digits=12, decimal_places=2)  # Preis je Anleihe
    issue_volume = models.DecimalField(max_digits=14, decimal_places=2)  # Emissionsvolumen

    term_months = models.PositiveSmallIntegerField()  # Laufzeit (Monate)
    minimal_bonds_quantity = models.PositiveIntegerField(
        default=1
    )  # Минимальное количество облигаций

    contract = models.JSONField(default=dict, blank=True)  # key->text (Textarea)
    active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "bond_issues"
        ordering = ["-issue_date", "-id"]

    def __str__(self) -> str:
        return f"{self.title} ({self.issue_date})"


class BondIssueAttachment(models.Model):
    issue = models.ForeignKey(
        BondIssue,
        on_delete=models.CASCADE,
        related_name="attachments",
    )
    file = models.FileField(upload_to="bond_issues/")
    description = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = "bond_issue_attachments"

    @property
    def filename(self):
        return os.path.basename(self.file.name)


class Contract(models.Model):
    contract_date = models.DateField()  # Datum des Vertrags

    settlement_date = models.DateField(null=True, blank=True)  # Расчетная дата
    bonds_quantity = models.PositiveIntegerField(null=True, blank=True)  # Количество облигаций
    nominal_amount = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)  # Номинальная сумма
    nominal_amount_plus_percent = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
    )  # Номинальная сумма плюс %

    issue = models.ForeignKey(
        BondIssue,
        on_delete=models.CASCADE,
        related_name="contracts",
    )
    client = models.ForeignKey(
        FlexxUser,
        on_delete=models.CASCADE,
        related_name="contracts_as_client",
    )

    pdf_file = models.FileField(upload_to=contract_pdf_upload_to, blank=True)

    signed_received_at = models.DateField(null=True, blank=True)
    paid_at = models.DateField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "contracts"
        ordering = ["-contract_date", "-id"]

    def __str__(self) -> str:
        return f"Contract#{self.id} issue={self.issue_id} client={self.client_id}"


class EmailTemplate(models.Model):
    class Party(models.TextChoices):
        FLEXXLAGER = "FleXXLager"
        TIPPGEBER = "Tippgeber"
        CLIENT = "Client"

    key = models.CharField(max_length=128, unique=True)  # e.g. send_password_reset_email
    from_role = models.CharField(max_length=20, choices=Party.choices)
    to_role = models.CharField(max_length=20, choices=Party.choices)

    subject = models.CharField(max_length=255)
    body_text = models.TextField()
    placeholder = models.CharField(max_length=128, blank=True)  # format: { placeholder }

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "email_templates"
        ordering = ["key"]

    def __str__(self) -> str:
        return self.key
