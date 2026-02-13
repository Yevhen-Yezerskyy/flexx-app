# FILE: web/flexx/emailer.py  (новое — 2026-02-13)
# PURPOSE: Центральная заглушка для отправки писем (пока без реальной отправки): регистрация принята, аккаунт ждёт активации.

from __future__ import annotations

import logging

log = logging.getLogger(__name__)


def send_registration_pending_email(*, to_email: str, role: str, first_name: str, last_name: str) -> None:
    subject = "Registrierung erhalten – Konto wartet auf Freischaltung"
    body = (
        f"Hallo {first_name} {last_name},\n\n"
        f"wir haben Ihre Registrierung ({role}) erhalten.\n"
        "Ihr Konto wartet auf Freischaltung. Wir melden uns, sobald es aktiviert ist.\n\n"
        "Mit freundlichen Grüßen\n"
        "FlexxLager Team\n"
    )
    log.info("[EMAIL:DUMMY] to=%s subject=%s\n%s", to_email, subject, body)
