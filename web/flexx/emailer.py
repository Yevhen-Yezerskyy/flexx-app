# FILE: web/flexx/emailer.py  (обновлено — 2026-02-13)
# PURPOSE: Добавлено логирование результата отправки (успех/ошибка) для любых писем.

from __future__ import annotations

import logging
from django.core.mail import EmailMultiAlternatives, get_connection

logger = logging.getLogger("flexx.emailer")

SMTP_HOST = "smtp.ionos.de"
SMTP_PORT = 587
SMTP_USER = "service@flexxlager.com"
SMTP_PASSWORD = "FlexxLagerService"
SMTP_USE_TLS = True
SMTP_USE_SSL = False

FROM_EMAIL = "FlexxLager Team <service@flexxlager.com>"
NOTIFY_EMAIL = "service@flexxlager.com"


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


def _send_text(*, to_email: str, subject: str, body: str) -> None:
    try:
        msg = EmailMultiAlternatives(
            subject=subject,
            body=body,
            from_email=FROM_EMAIL,
            to=[to_email],
            connection=_conn(),
        )
        sent_count = msg.send()
        if sent_count == 1:
            logger.info("EMAIL_SENT to=%s subject=%s", to_email, subject)
        else:
            logger.error("EMAIL_NOT_SENT to=%s subject=%s sent_count=%s", to_email, subject, sent_count)
    except Exception as e:
        logger.exception("EMAIL_ERROR to=%s subject=%s error=%s", to_email, subject, str(e))
        raise


def send_registration_pending_email(*, to_email: str, role: str, first_name: str, last_name: str) -> None:
    subject = "Registrierung erhalten – Konto wartet auf Freischaltung"
    body = (
        f"Hallo {first_name} {last_name},\n\n"
        f"wir haben Ihre Registrierung ({role}) erhalten.\n"
        "Ihr Konto wartet auf Freischaltung. Wir melden uns, sobald es aktiviert ist.\n\n"
        "Mit freundlichen Grüßen\n"
        "FlexxLager Team\n"
    )
    _send_text(to_email=to_email, subject=subject, body=body)


def send_registration_notify_email(*, role: str, user_email: str, first_name: str, last_name: str) -> None:
    subject = "Neue Registrierung"
    body = (
        "Neue Registrierung im System.\n\n"
        f"Name: {first_name} {last_name}\n"
        f"E-Mail: {user_email}\n"
        f"Rolle: {role}\n"
    )
    _send_text(to_email=NOTIFY_EMAIL, subject=subject, body=body)


def send_password_reset_email(*, to_email: str, first_name: str, last_name: str, reset_url: str) -> None:
    subject = "Passwort zurücksetzen"
    body = (
        f"Hallo {first_name} {last_name},\n\n"
        "Sie haben eine Passwort-Zurücksetzung angefordert.\n"
        f"Link: {reset_url}\n\n"
        "Wenn Sie das nicht waren, ignorieren Sie diese E-Mail.\n\n"
        "Mit freundlichen Grüßen\n"
        "FlexxLager Team\n"
    )
    _send_text(to_email=to_email, subject=subject, body=body)
