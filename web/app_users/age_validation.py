from __future__ import annotations

from datetime import date

from django.core.exceptions import ValidationError
from django.forms import DateField
from django.utils import timezone


def adult_birth_date_cutoff() -> date:
    today = timezone.localdate()
    try:
        return today.replace(year=today.year - 18)
    except ValueError:
        return today.replace(year=today.year - 18, day=28)


def validate_adult_birth_date(value: date | None) -> None:
    if not value:
        return

    today = timezone.localdate()
    age = today.year - value.year - ((today.month, today.day) < (value.month, value.day))
    if age < 18:
        raise ValidationError("Sie müssen mindestens 18 Jahre alt sein.")


def apply_birth_date_constraints(field: DateField, *, required: bool) -> None:
    field.error_messages["invalid"] = "Bitte geben Sie ein gültiges Datum ein."
    if required:
        field.error_messages["required"] = "Bitte geben Sie Geburtsdatum an."
    field.widget.attrs["max"] = adult_birth_date_cutoff().isoformat()
