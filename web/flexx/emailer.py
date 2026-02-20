# FILE: web/flexx/emailer.py  (обновлено — 2026-02-15)
# PURPOSE: Fix: активационные письма разделены (Kunde/Tippgeber); send_account_activated_email обратно-совместим (role optional).

from __future__ import annotations

from datetime import date
import logging
import os

from django.core.mail import EmailMultiAlternatives, get_connection

logger = logging.getLogger(__name__)

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.ionos.de")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "service@flexxlager.com")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "FlexxLagerService")
SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "1").strip().lower() in ("1", "true", "yes", "y", "on")
SMTP_USE_SSL = os.getenv("SMTP_USE_SSL", "0").strip().lower() in ("1", "true", "yes", "y", "on")

FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "FlexxLager Team <service@flexxlager.com>")
NOTIFY_EMAIL = os.getenv("NOTIFY_EMAIL", "service@flexxlager.com")


class EmailSendError(RuntimeError):
    pass


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
        if not ok:
            logger.error("EMAIL_FAIL to=%s subject=%s sent_count=%s", to_email, subject, sent_count)
            raise EmailSendError(f"Email not sent: to={to_email} subject={subject} sent_count={sent_count}")
        logger.info("EMAIL_OK to=%s subject=%s", to_email, subject)
        return True
    except Exception as e:
        logger.exception("EMAIL_ERROR to=%s subject=%s", to_email, subject)
        raise EmailSendError(f"Email send error: to={to_email} subject={subject}") from e


# ---- registration / admin activation ----

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


def send_account_activated_email(
    *,
    to_email: str,
    first_name: str,
    last_name: str,
    role: str = "",
    set_password_url: str = "",
) -> bool:
    """Backward-compatible: role optional (older code called without it)."""

    subject = "Konto freigeschaltet"
    role_part = f" ({role})" if (role or "").strip() else ""
    link_block = ""
    if (set_password_url or "").strip():
        link_block = (
            "Bitte erstellen Sie jetzt Ihr Passwort über den folgenden einmaligen Link:\n"
            f"{set_password_url}\n\n"
            "Nach dem Setzen des Passworts können Sie sich direkt anmelden.\n\n"
        )

    body = (
        f"Hallo {first_name} {last_name},\n\n"
        f"Ihr Konto{role_part} wurde freigeschaltet.\n\n"
        f"{link_block}"
        "Mit freundlichen Grüßen\n"
        "FlexxLager Team\n"
    )
    return _send_text(to_email=to_email, subject=subject, body=body)


def send_client_activated_email(
    *,
    to_email: str,
    first_name: str,
    last_name: str,
    set_password_url: str = "",
) -> bool:
    return send_account_activated_email(
        to_email=to_email,
        first_name=first_name,
        last_name=last_name,
        role="Kunde",
        set_password_url=set_password_url,
    )


def send_tippgeber_activated_email(
    *,
    to_email: str,
    first_name: str,
    last_name: str,
    set_password_url: str = "",
) -> bool:
    return send_account_activated_email(
        to_email=to_email,
        first_name=first_name,
        last_name=last_name,
        role="Tippgeber",
        set_password_url=set_password_url,
    )


def send_account_deactivated_email(*, to_email: str, role: str, first_name: str, last_name: str) -> bool:
    subject = "Konto deaktiviert"
    body = (
        f"Hallo {first_name} {last_name},\n\n"
        f"Ihr Konto ({role}) wurde deaktiviert.\n"
        "Bitte kontaktieren Sie uns bei Fragen.\n\n"
        "Mit freundlichen Grüßen\n"
        "FlexxLager Team\n"
    )
    return _send_text(to_email=to_email, subject=subject, body=body)


# ---- password flows ----

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


# ---- Tippgeber flows ----

def send_tippgeber_added_interessent_email(
    *,
    tippgeber_email: str,
    tippgeber_first_name: str,
    tippgeber_last_name: str,
    client_email: str,
    client_first_name: str,
    client_last_name: str,
) -> bool:
    subject = "Neuer Interessent durch Tippgeber"
    body = (
        "Ein Tippgeber hat einen Interessenten übermittelt.\n\n"
        f"Tippgeber: {tippgeber_first_name} {tippgeber_last_name} <{tippgeber_email}>\n"
        f"Interessent: {client_first_name} {client_last_name} <{client_email}>\n"
    )
    return _send_text(to_email=NOTIFY_EMAIL, subject=subject, body=body)


def send_tippgeber_link_conflict_email(
    *,
    tippgeber_email: str,
    tippgeber_first_name: str,
    tippgeber_last_name: str,
    client_email: str,
    client_first_name: str,
    client_last_name: str,
) -> bool:
    subject = "Konflikt: Kunde existiert bereits"
    body = (
        "Ein Tippgeber wollte einen bereits vorhandenen Kunden zuordnen (Zuordnung wurde NICHT erstellt).\n\n"
        f"Tippgeber: {tippgeber_first_name} {tippgeber_last_name} <{tippgeber_email}>\n"
        f"Kunde: {client_first_name} {client_last_name} <{client_email}>\n"
    )
    return _send_text(to_email=NOTIFY_EMAIL, subject=subject, body=body)


# ---- Contract status flows ----

def send_contract_signed_received_email(
    *,
    to_email: str,
    first_name: str,
    last_name: str,
    contract_id: int,
    issue_title: str,
    signed_date: date,
) -> bool:
    subject = "Vertrag erhalten"
    body = (
        f"Hallo {first_name} {last_name},\n\n"
        "wir bestätigen den Eingang Ihres unterzeichneten Vertrags.\n"
        f"Vertrag: #{contract_id}\n"
        f"Emission: {issue_title}\n"
        f"Eingang am: {signed_date:%d.%m.%Y}\n\n"
        "Mit freundlichen Grüßen\n"
        "FlexxLager Team\n"
    )
    return _send_text(to_email=to_email, subject=subject, body=body)


def send_contract_paid_received_email(
    *,
    to_email: str,
    first_name: str,
    last_name: str,
    contract_id: int,
    issue_title: str,
    paid_date: date,
) -> bool:
    subject = "Zahlung erhalten"
    body = (
        f"Hallo {first_name} {last_name},\n\n"
        "wir bestätigen den Eingang Ihrer Zahlung.\n"
        f"Vertrag: #{contract_id}\n"
        f"Emission: {issue_title}\n"
        f"Eingang am: {paid_date:%d.%m.%Y}\n\n"
        "Mit freundlichen Grüßen\n"
        "FlexxLager Team\n"
    )
    return _send_text(to_email=to_email, subject=subject, body=body)


# ---- Client self-service contract flow (notify internal) ----

def send_client_profile_completed_notify_email(
    *,
    client_email: str,
    first_name: str,
    last_name: str,
) -> bool:
    subject = "Kunde hat Profil vervollständigt"
    body = (
        "Ein Kunde hat sein Profil vollständig ausgefüllt.\n\n"
        f"Kunde: {first_name} {last_name} <{client_email}>\n"
    )
    return _send_text(to_email=NOTIFY_EMAIL, subject=subject, body=body)


def send_client_contract_created_notify_email(
    *,
    client_email: str,
    first_name: str,
    last_name: str,
    contract_id: int,
    issue_title: str,
) -> bool:
    subject = "Kunde hat Vertrag erstellt"
    body = (
        "Ein Kunde hat einen Vertrag erstellt.\n\n"
        f"Kunde: {first_name} {last_name} <{client_email}>\n"
        f"Vertrag: #{contract_id}\n"
        f"Emission: {issue_title}\n"
    )
    return _send_text(to_email=NOTIFY_EMAIL, subject=subject, body=body)


def send_client_contract_deleted_notify_email(
    *,
    client_email: str,
    first_name: str,
    last_name: str,
    contract_id: int,
    issue_title: str,
) -> bool:
    subject = "Kunde hat Vertrag gelöscht"
    body = (
        "Ein Kunde hat einen Vertrag gelöscht.\n\n"
        f"Kunde: {first_name} {last_name} <{client_email}>\n"
        f"Vertrag: #{contract_id}\n"
        f"Emission: {issue_title}\n"
    )
    return _send_text(to_email=NOTIFY_EMAIL, subject=subject, body=body)
