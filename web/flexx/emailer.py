# FILE: web/flexx/emailer.py  (обновлено — 2026-02-13)
# PURPOSE: Письма: возвращаем True/False (успех), логируем только итог (OK/FAIL/ERROR), добавлено письмо "установить пароль".

from __future__ import annotations

import logging
import os

from django.core.mail import EmailMultiAlternatives, get_connection

logger = logging.getLogger(__name__)

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.ionos.de")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "service@flexxlager.com")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "FlexxLagerService")
SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "1").lower() in ("1", "true", "yes", "y", "on")
SMTP_USE_SSL = os.getenv("SMTP_USE_SSL", "0").lower() in ("1", "true", "yes", "y", "on")

FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "FlexxLager Team <service@flexxlager.com>")
NOTIFY_EMAIL = os.getenv("NOTIFY_EMAIL", "service@flexxlager.com")


def _conn():
    return get_connection(
        host=SMTP_HOST,
        port=SMTP_PORT,
        username=SMTP_USER,
        password=SMTP_PASSWORD,
        use_tls=SMTP_USE_TLS,
        use_ssl=SMTP_USE_SSL,
        fail_silently=False,
    )


def _send_text(*, to_email: str, subject: str, body: str) -> bool:
    try:
        msg = EmailMultiAlternatives(
            subject=subject,
            body=body,
            from_email=FROM_EMAIL,
            to=[to_email],
            connection=_conn(),
        )
        sent_count = msg.send()
        ok = sent_count == 1
        if ok:
            logger.info("EMAIL_OK to=%s subject=%s", to_email, subject)
        else:
            logger.error("EMAIL_FAIL to=%s subject=%s sent_count=%s", to_email, subject, sent_count)
        return ok
    except Exception:
        logger.exception("EMAIL_ERROR to=%s subject=%s", to_email, subject)
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
        "Neue Registrierung im System.\n\n"
        f"Name: {first_name} {last_name}\n"
        f"E-Mail: {user_email}\n"
        f"Rolle: {role}\n"
    )
    return _send_text(to_email=NOTIFY_EMAIL, subject=subject, body=body)


def send_password_reset_email(*, to_email: str, first_name: str, last_name: str, reset_url: str) -> bool:
    subject = "Passwort zurücksetzen"
    body = (
        f"Hallo {first_name} {last_name},\n\n"
        "Sie haben eine Passwort-Zurücksetzung angefordert.\n"
        f"Link: {reset_url}\n\n"
        "Wenn Sie das nicht waren, ignorieren Sie diese E-Mail.\n\n"
        "Mit freundlichen Grüßen\n"
        "FlexxLager Team\n"
    )
    return _send_text(to_email=to_email, subject=subject, body=body)


def send_set_password_email(*, to_email: str, first_name: str, last_name: str, set_url: str) -> bool:
    subject = "Passwort festlegen"
    body = (
        f"Hallo {first_name} {last_name},\n\n"
        "Bitte legen Sie Ihr Passwort fest.\n"
        f"Link: {set_url}\n\n"
        "Dieser Link ist nur einmal nutzbar.\n\n"
        "Mit freundlichen Grüßen\n"
        "FlexxLager Team\n"
    )
    return _send_text(to_email=to_email, subject=subject, body=body)
