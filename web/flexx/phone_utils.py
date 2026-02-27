from __future__ import annotations

import phonenumbers
from phonenumbers import NumberParseException, PhoneNumberFormat


def format_phone_international(value: str | None, *, default_region: str = "DE") -> str:
    raw = (value or "").strip()
    if not raw:
        return ""

    normalized = raw.replace("(0)", "")
    if normalized.startswith("00"):
        normalized = f"+{normalized[2:]}"

    try:
        parsed = phonenumbers.parse(
            normalized,
            None if normalized.lstrip().startswith("+") else default_region,
        )
        if not phonenumbers.is_possible_number(parsed):
            return raw
        return phonenumbers.format_number(parsed, PhoneNumberFormat.INTERNATIONAL)
    except NumberParseException:
        return raw
