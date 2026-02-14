# FILE: web/flexx/emailer.py  (обновлено — 2026-02-14)
# PURPOSE: Добавлено письмо "Konto aktiviert" для Tippgeber (Agent).

from __future__ import annotations

import logging
import os

from django.core.mail import EmailMultiAlternatives, get_connection

logger = logging.getLogger(__name__)

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.ionos.de")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "1").strip().lower() in ("1", "true", "yes", "y", "on")

FROM_EMAIL = os.getenv("FROM_EMAIL", SMTP_USER or "noreply@flexxlager.de")


def _conn():
    return get_connection(
        host=SMTP_HOST,
        port=SMTP_PORT,
        username=SMTP_USER,
        password=SMTP_PASSWORD,
        use_tls=SMTP_USE_TLS,
        fail_silently=False,
    )


def _send_text(*, to_email: str, subject: str, body: str) -> bool:
    try:
        msg = EmailMultiAlternatives(subject=subject, body=body, from_email=FROM_EMAIL, to=[to_email], connection=_conn())
        msg.send(fail_silently=False)
        logger.info("EMAIL OK to=%s subject=%s", to_email, subject)
        return True
    except Exception:
        logger.exception("EMAIL ERROR to=%s subject=%s", to_email, subject)
        return False


def send_registration_pending_email(*, to_email: str, role: str, first_name: str, last_name: str) -> bool:
    subject = "Registrierung erhalten – Konto wartet auf Freischaltung"
    body = (
        f"Hallo {first_name} {last_name},\n\n"
        f"wir haben Ihre Registrierung ({role}) erhalten.\n"
        "Ihr Konto wartet auf Freischaltung. Wir melden uns, sobald es aktiviert ist.\n\n"
        "Mit freundlichen Grüßen\n"
        "FlexxLager Team\n"
    )
    return _send_text(to_email=to_email, subject=subject, body=body)


def send_registration_notify_email(*, role: str, user_email: str, first_name: str, last_name: str) -> bool:
    subject = "Neue Registrierung"
    body = (
        "Neue Registrierung:\n\n"
        f"Rolle: {role}\n"
        f"E-Mail: {user_email}\n"
        f"Name: {first_name} {last_name}\n"
    )
    return _send_text(to_email=FROM_EMAIL, subject=subject, body=body)


def send_password_reset_email(*, to_email: str, reset_link: str, expires_in_days: int) -> bool:
    subject = "Passwort zurücksetzen"
    body = (
        "Hallo,\n\n"
        "Sie haben eine Anfrage zum Zurücksetzen Ihres Passworts gestellt.\n\n"
        f"Link: {reset_link}\n"
        f"Gültig: {expires_in_days} Tage\n\n"
        "Wenn Sie diese Anfrage nicht gestellt haben, ignorieren Sie diese E-Mail.\n\n"
        "Mit freundlichen Grüßen\n"
        "FlexxLager Team\n"
    )
    return _send_text(to_email=to_email, subject=subject, body=body)


def send_set_password_email(*, to_email: str, set_password_link: str, expires_in_days: int) -> bool:
    subject = "Passwort festlegen"
    body = (
        "Hallo,\n\n"
        "Bitte legen Sie Ihr Passwort fest.\n\n"
        f"Link: {set_password_link}\n"
        f"Gültig: {expires_in_days} Tage\n\n"
        "Mit freundlichen Grüßen\n"
        "FlexxLager Team\n"
    )
    return _send_text(to_email=to_email, subject=subject, body=body)


def send_account_activated_email(*, to_email: str, first_name: str, last_name: str) -> bool:
    subject = "Ihr Konto wurde aktiviert"
    body = (
        f"Hallo {first_name} {last_name},\n\n"
        "Ihr Konto wurde aktiviert. Sie können sich jetzt anmelden.\n\n"
        "Mit freundlichen Grüßen\n"
        "FlexxLager Team\n"
    )
    return _send_text(to_email=to_email, subject=subject, body=body)
