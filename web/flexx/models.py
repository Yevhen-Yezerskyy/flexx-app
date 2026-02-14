# FILE: web/flexx/models.py  (обновлено — 2026-02-14)
# PURPOSE: Общие модели: BondIssue (Platzierung) без extra_term_months + BondIssueAttachment (файлы N шт. с описанием).

from __future__ import annotations

from django.db import models


def bond_issue_attachment_upload_to(instance: "BondIssueAttachment", filename: str) -> str:
    return f"bond_issues/{instance.issue_id}/{filename}"


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
    issue = models.ForeignKey(BondIssue, on_delete=models.CASCADE, related_name="attachments")
    file = models.FileField(upload_to=bond_issue_attachment_upload_to)
    description = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "bond_issue_attachments"
        ordering = ["id"]

    def __str__(self) -> str:
        return f"Attachment #{self.id} for issue_id={self.issue_id}"
