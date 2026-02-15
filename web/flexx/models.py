# FILE: web/flexx/models.py  (обновлено — 2026-02-15)
# PURPOSE: Оставлено без изменений: BondIssue + BondIssueAttachment (как в архиве); добавлено: Contract (договор клиента по эмиссии, PDF, даты подписания/оплаты).

from __future__ import annotations

from django.db import models
import os

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
        import os
        return os.path.basename(self.file.name)


class Contract(models.Model):
    contract_date = models.DateField()  # Datum des Vertrags

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

    pdf_file = models.FileField(upload_to=contract_pdf_upload_to, blank=True)  # PDF-Link

    signed_received_at = models.DateField(null=True, blank=True)  # Unterschrieben erhalten (Datum)
    paid_at = models.DateField(null=True, blank=True)  # Bezahlt (Datum)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "contracts"
        ordering = ["-contract_date", "-id"]

    def __str__(self) -> str:
        return f"Contract#{self.id} issue={self.issue_id} client={self.client_id}"
