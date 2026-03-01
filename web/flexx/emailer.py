# FILE: web/flexx/emailer.py  (обновлено — 2026-02-15)
# PURPOSE: Fix: активационные письма разделены (Kunde/Tippgeber); send_account_activated_email обратно-совместим (role optional).

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from email.utils import formataddr, parseaddr
import imaplib
import logging
import os
import re
import time

from django.core.mail import EmailMultiAlternatives, get_connection
from django.utils import timezone
from .models import EmailTemplate

logger = logging.getLogger(__name__)

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.ionos.de")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "service@flexxlager.com")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "FlexxLagerService")
SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "1").strip().lower() in ("1", "true", "yes", "y", "on")
SMTP_USE_SSL = os.getenv("SMTP_USE_SSL", "0").strip().lower() in ("1", "true", "yes", "y", "on")
IMAP_HOST = os.getenv("IMAP_HOST", "imap.ionos.de")
IMAP_PORT = int(os.getenv("IMAP_PORT", "993"))
IMAP_SENT_FOLDER = os.getenv("IMAP_SENT_FOLDER", "SendLog")

FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "FlexxLager Team <service@flexxlager.com>")
NOTIFY_EMAIL = os.getenv("NOTIFY_EMAIL", "service@flexxlager.com")


class EmailSendError(RuntimeError):
    pass


EMAIL_TEMPLATE_NOT_FOUND = "NOT_FOUND"
EMAIL_TEMPLATE_SEND_ERROR = "SEND_ERROR"
EMAIL_TEMPLATE_SENT = "SENT"


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


def _append_to_sent(raw_message: bytes) -> None:
    imap = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
    try:
        imap.login(SMTP_USER, SMTP_PASSWORD)
        try:
            imap.create(IMAP_SENT_FOLDER)
        except Exception:
            pass
        imap.append(
            IMAP_SENT_FOLDER,
            "\\Seen",
            imaplib.Time2Internaldate(time.time()),
            raw_message,
        )
    finally:
        try:
            imap.logout()
        except Exception:
            pass


def _send_text(
    *,
    to_email: str,
    subject: str,
    body: str,
    from_email: str | None = None,
    attachments: Sequence[tuple[str, bytes, str]] | None = None,
) -> bool:
    try:
        effective_from_email = from_email or FROM_EMAIL
        msg = EmailMultiAlternatives(
            subject=subject,
            body=body,
            from_email=effective_from_email,
            to=[to_email],
            connection=_conn(),
        )
        for filename, content, mimetype in attachments or ():
            msg.attach(filename, content, mimetype)
        raw_message = msg.message().as_bytes()
        sent_count = msg.send()
        ok = sent_count == 1
        if not ok:
            logger.error("EMAIL_FAIL to=%s subject=%s sent_count=%s", to_email, subject, sent_count)
            raise EmailSendError(f"Email not sent: to={to_email} subject={subject} sent_count={sent_count}")
        try:
            _append_to_sent(raw_message)
        except Exception:
            pass
        logger.info("EMAIL_OK to=%s subject=%s", to_email, subject)
        return True
    except Exception as e:
        logger.exception("EMAIL_ERROR to=%s subject=%s", to_email, subject)
        raise EmailSendError(f"Email send error: to={to_email} subject={subject}") from e


def send_email_from_template(
    *,
    key: str,
    to_email: str,
    context: Mapping[str, object] | None = None,
    attachments: Sequence[tuple[str, bytes, str]] | None = None,
) -> str:
    template = (
        EmailTemplate.objects.filter(key=key, is_active=True)
        .only("subject", "body_text", "from_text")
        .first()
    )
    if template is None:
        logger.warning("EMAIL_TEMPLATE_NOT_FOUND key=%s to=%s", key, to_email)
        return EMAIL_TEMPLATE_NOT_FOUND

    ctx = context or {}
    placeholder_re = re.compile(r"\{\s*([a-zA-Z0-9_]+)\s*\}")

    subject = placeholder_re.sub(
        lambda m: (
            m.group(0)
            if m.group(1) not in ctx
            else ("" if ctx[m.group(1)] is None else str(ctx[m.group(1)]))
        ),
        template.subject,
    )
    body = placeholder_re.sub(
        lambda m: (
            m.group(0)
            if m.group(1) not in ctx
            else ("" if ctx[m.group(1)] is None else str(ctx[m.group(1)]))
        ),
        template.body_text,
    )

    display_name = (template.from_text or "").strip()
    from_email = FROM_EMAIL
    if display_name:
        _, base_email = parseaddr(FROM_EMAIL)
        if base_email:
            from_email = formataddr((display_name, base_email))

    try:
        _send_text(
            to_email=to_email,
            subject=subject,
            body=body,
            from_email=from_email,
            attachments=attachments,
        )
        return EMAIL_TEMPLATE_SENT
    except EmailSendError:
        logger.error("EMAIL_TEMPLATE_SEND_ERROR key=%s to=%s", key, to_email)
        return EMAIL_TEMPLATE_SEND_ERROR


# ---- registration / admin activation ----

def send_registration_pending_client_email(*, to_email: str, first_name: str, last_name: str) -> bool:
    client_name = f"{first_name} {last_name}".strip()
    status = send_email_from_template(
        key=send_registration_pending_client_email.__name__,
        to_email=to_email,
        context={"client_name": client_name},
    )
    if status == EMAIL_TEMPLATE_SENT:
        return True
    if status == EMAIL_TEMPLATE_SEND_ERROR:
        raise EmailSendError(
            f"Template email send error: key={send_registration_pending_client_email.__name__} to={to_email}"
        )

    subject = "Ihre Registrierung bei FleXXLager – Konto in Prüfung"
    body = (
        f"Sehr geehrte/r {client_name},\n\n"
        "vielen Dank für Ihre Registrierung als Kunde bei FleXXLager.\n"
        "Ihr Benutzerkonto wurde erfolgreich erstellt und befindet sich derzeit in Prüfung.\n"
        "Sobald die Freischaltung erfolgt ist, erhalten Sie eine separate Benachrichtigung.\n\n"
        "Mit freundlichen Grüßen\n"
        "Ihr FleXXLager Team\n"
    )
    _, base_email = parseaddr(FROM_EMAIL)
    from_email = formataddr(("FleXXLager Team", base_email)) if base_email else FROM_EMAIL
    return _send_text(to_email=to_email, subject=subject, body=body, from_email=from_email)


def send_registration_pending_tippgeber_email(*, to_email: str, first_name: str, last_name: str) -> bool:
    tippgeber_name = f"{first_name} {last_name}".strip()
    status = send_email_from_template(
        key=send_registration_pending_tippgeber_email.__name__,
        to_email=to_email,
        context={"tippgeber_name": tippgeber_name},
    )
    if status == EMAIL_TEMPLATE_SENT:
        return True
    if status == EMAIL_TEMPLATE_SEND_ERROR:
        raise EmailSendError(
            f"Template email send error: key={send_registration_pending_tippgeber_email.__name__} to={to_email}"
        )

    subject = "Ihre Registrierung bei FleXXLager – Konto in Prüfung"
    body = (
        f"Sehr geehrte/r {tippgeber_name},\n\n"
        "vielen Dank für Ihre Registrierung als Tippgeber bei FleXXLager.\n"
        "Ihr Benutzerkonto wurde erfolgreich erstellt und befindet sich derzeit in Prüfung.\n"
        "Sobald die Freischaltung erfolgt ist, erhalten Sie eine separate Benachrichtigung.\n\n"
        "Mit freundlichen Grüßen\n"
        "Ihr FleXXLager Team\n"
    )
    _, base_email = parseaddr(FROM_EMAIL)
    from_email = formataddr(("FleXXLager Team", base_email)) if base_email else FROM_EMAIL
    return _send_text(to_email=to_email, subject=subject, body=body, from_email=from_email)


def send_registration_notify_client_email(*, user_email: str, first_name: str, last_name: str) -> bool:
    client_name = f"{first_name} {last_name}".strip()
    registered_at = timezone.localtime(timezone.now()).strftime("%d.%m.%Y %H:%M")
    client = (
        f"Name: {client_name}\n"
        f"Mail: {user_email}\n"
        f"Registrierung: {registered_at}"
    )

    status = send_email_from_template(
        key=send_registration_notify_client_email.__name__,
        to_email=NOTIFY_EMAIL,
        context={"client": client},
    )
    if status == EMAIL_TEMPLATE_SENT:
        return True
    if status == EMAIL_TEMPLATE_SEND_ERROR:
        raise EmailSendError(
            f"Template email send error: key={send_registration_notify_client_email.__name__} to={NOTIFY_EMAIL}"
        )

    subject = "Neuer Kunde registriert – Bitte prüfen"
    body = (
        "Guten Tag,\n\n"
        "im System hat sich ein neuer Kunde registriert:\n"
        f"{client}\n\n"
        "Bitte prüfen Sie die Registrierung und aktivieren Sie den Kunden, sofern alles passt.\n\n"
        "Mit freundlichen Grüßen\n"
        "FleXXLager CRM\n"
    )
    _, base_email = parseaddr(FROM_EMAIL)
    from_email = formataddr(("FleXXLager CRM (Client)", base_email)) if base_email else FROM_EMAIL
    return _send_text(to_email=NOTIFY_EMAIL, subject=subject, body=body, from_email=from_email)


def send_registration_notify_tippgeber_email(*, user_email: str, first_name: str, last_name: str) -> bool:
    tippgeber_name = f"{first_name} {last_name}".strip()
    registered_at = timezone.localtime(timezone.now()).strftime("%d.%m.%Y %H:%M")
    tippgeber = (
        f"Name: {tippgeber_name}\n"
        f"Mail: {user_email}\n"
        f"Registrierung: {registered_at}"
    )

    status = send_email_from_template(
        key=send_registration_notify_tippgeber_email.__name__,
        to_email=NOTIFY_EMAIL,
        context={"tippgeber": tippgeber},
    )
    if status == EMAIL_TEMPLATE_SENT:
        return True
    if status == EMAIL_TEMPLATE_SEND_ERROR:
        raise EmailSendError(
            f"Template email send error: key={send_registration_notify_tippgeber_email.__name__} to={NOTIFY_EMAIL}"
        )

    subject = "Neuer Tippgeber registriert – Bitte prüfen"
    body = (
        "Guten Tag,\n\n"
        "im System hat sich ein neuer Tippgeber registriert:\n"
        f"{tippgeber}\n\n"
        "Bitte prüfen Sie die Registrierung und aktivieren Sie den Tippgeber, sofern alles passt.\n\n"
        "Mit freundlichen Grüßen\n"
        "FleXXLager CRM\n"
    )
    _, base_email = parseaddr(FROM_EMAIL)
    from_email = formataddr(("FleXXLager CRM (Tippgeber)", base_email)) if base_email else FROM_EMAIL
    return _send_text(to_email=NOTIFY_EMAIL, subject=subject, body=body, from_email=from_email)


def send_client_activated_with_password_email(
    *,
    to_email: str,
    first_name: str,
    last_name: str,
    set_password_url: str,
) -> bool:
    status = send_email_from_template(
        key=send_client_activated_with_password_email.__name__,
        to_email=to_email,
        context={"link": set_password_url},
    )
    if status == EMAIL_TEMPLATE_SENT:
        return True
    if status == EMAIL_TEMPLATE_SEND_ERROR:
        raise EmailSendError(
            f"Template email send error: key={send_client_activated_with_password_email.__name__} to={to_email}"
        )

    subject = "Ihr Zugang zu FleXXLager"
    body = (
        "Sehr geehrte/r Kunde/Kundin,\n\n"
        "Sie wurden im System FleXXLager registriert. Ihr Benutzerkonto wurde bereits aktiviert.\n"
        "Bitte nutzen Sie folgenden Link, um Ihr persönliches Passwort festzulegen:\n\n"
        f"{set_password_url}\n\n"
        "Der Link zur Einrichtung Ihres Passworts ist 7 Tage gültig. Sollten Sie die E-Mail verlieren "
        "oder Ihr Passwort nicht rechtzeitig festlegen, können Sie jederzeit die Funktion "
        "„Passwort vergessen“ nutzen, um einen neuen Link anzufordern.\n\n"
        "Anschließend können Sie sich mit Ihrer E-Mail-Adresse und Ihrem Passwort im FleXXLager-System anmelden.\n\n"
        "Sollten Sie kein Interesse an einer Zusammenarbeit haben oder irrtümlich registriert worden sein, "
        "bitten wir um Entschuldigung. Antworten Sie in diesem Fall bitte kurz auf diese E-Mail mit "
        "„Nicht interessiert“ oder „Fehler“, und wir werden Ihre personenbezogenen Daten umgehend löschen.\n\n"
        "Mit freundlichen Grüßen\n"
        "Ihr FleXXLager Team\n"
    )
    _, base_email = parseaddr(FROM_EMAIL)
    from_email = formataddr(("FleXXLager Team", base_email)) if base_email else FROM_EMAIL
    return _send_text(to_email=to_email, subject=subject, body=body, from_email=from_email)


def send_client_activated_without_password_email(
    *,
    to_email: str,
    first_name: str,
    last_name: str,
) -> bool:
    client_name = f"{first_name} {last_name}".strip()
    status = send_email_from_template(
        key=send_client_activated_without_password_email.__name__,
        to_email=to_email,
        context={"client_name": client_name},
    )
    if status == EMAIL_TEMPLATE_SENT:
        return True
    if status == EMAIL_TEMPLATE_SEND_ERROR:
        raise EmailSendError(
            f"Template email send error: key={send_client_activated_without_password_email.__name__} to={to_email}"
        )

    subject = "Ihr Konto wurde aktiviert"
    body = (
        f"Sehr geehrte/r {client_name},\n\n"
        "Ihr Benutzerkonto wurde erfolgreich aktiviert.\n"
        "Bitte verwenden Sie Ihre Zugangsdaten (E-Mail und Passwort), um sich anzumelden.\n\n"
        "Mit freundlichen Grüßen\n"
        "Ihr FleXXLager Team\n"
    )
    _, base_email = parseaddr(FROM_EMAIL)
    from_email = formataddr(("FleXXLager Team", base_email)) if base_email else FROM_EMAIL
    return _send_text(to_email=to_email, subject=subject, body=body, from_email=from_email)


def send_tippgeber_activated_with_password_email(
    *,
    to_email: str,
    first_name: str,
    last_name: str,
    set_password_url: str,
) -> bool:
    status = send_email_from_template(
        key=send_tippgeber_activated_with_password_email.__name__,
        to_email=to_email,
        context={"link": set_password_url},
    )
    if status == EMAIL_TEMPLATE_SENT:
        return True
    if status == EMAIL_TEMPLATE_SEND_ERROR:
        raise EmailSendError(
            f"Template email send error: key={send_tippgeber_activated_with_password_email.__name__} to={to_email}"
        )

    subject = "Ihr Zugang zu FleXXLager"
    body = (
        "Sehr geehrte/r Tippgeber/in,\n\n"
        "Sie wurden im System FleXXLager registriert. Ihr Benutzerkonto wurde bereits aktiviert.\n"
        "Bitte nutzen Sie folgenden Link, um Ihr persönliches Passwort festzulegen:\n\n"
        f"{set_password_url}\n\n"
        "Der Link zur Einrichtung Ihres Passworts ist 7 Tage gültig. Sollten Sie die E-Mail verlieren "
        "oder Ihr Passwort nicht rechtzeitig festlegen, können Sie jederzeit die Funktion "
        "„Passwort vergessen“ nutzen, um einen neuen Link anzufordern.\n\n"
        "Anschließend können Sie sich mit Ihrer E-Mail-Adresse und Ihrem Passwort im FleXXLager-System anmelden.\n\n"
        "Sollten Sie kein Interesse an einer Zusammenarbeit haben oder irrtümlich registriert worden sein, "
        "bitten wir um Entschuldigung. Antworten Sie in diesem Fall bitte kurz auf diese E-Mail mit "
        "„Nicht interessiert“ oder „Fehler“, und wir werden Ihre personenbezogenen Daten umgehend löschen.\n\n"
        "Mit freundlichen Grüßen\n"
        "Ihr FleXXLager Team\n"
    )
    _, base_email = parseaddr(FROM_EMAIL)
    from_email = formataddr(("FleXXLager Team", base_email)) if base_email else FROM_EMAIL
    return _send_text(to_email=to_email, subject=subject, body=body, from_email=from_email)


def send_tippgeber_activated_without_password_email(
    *,
    to_email: str,
    first_name: str,
    last_name: str,
) -> bool:
    tippgeber_name = f"{first_name} {last_name}".strip()
    status = send_email_from_template(
        key=send_tippgeber_activated_without_password_email.__name__,
        to_email=to_email,
        context={"client_name": tippgeber_name},
    )
    if status == EMAIL_TEMPLATE_SENT:
        return True
    if status == EMAIL_TEMPLATE_SEND_ERROR:
        raise EmailSendError(
            f"Template email send error: key={send_tippgeber_activated_without_password_email.__name__} to={to_email}"
        )

    subject = "Ihr Konto wurde aktiviert"
    body = (
        f"Sehr geehrte/r {tippgeber_name},\n\n"
        "Ihr Benutzerkonto wurde erfolgreich aktiviert.\n"
        "Bitte verwenden Sie Ihre Zugangsdaten (E-Mail und Passwort), um sich anzumelden.\n\n"
        "Mit freundlichen Grüßen\n"
        "Ihr FleXXLager Team\n"
    )
    _, base_email = parseaddr(FROM_EMAIL)
    from_email = formataddr(("FleXXLager Team", base_email)) if base_email else FROM_EMAIL
    return _send_text(to_email=to_email, subject=subject, body=body, from_email=from_email)


def send_client_activated_email(
    *,
    to_email: str,
    first_name: str,
    last_name: str,
    set_password_url: str = "",
) -> bool:
    if (set_password_url or "").strip():
        return send_client_activated_with_password_email(
            to_email=to_email,
            first_name=first_name,
            last_name=last_name,
            set_password_url=set_password_url,
        )
    return send_client_activated_without_password_email(
        to_email=to_email,
        first_name=first_name,
        last_name=last_name,
    )


def send_tippgeber_activated_email(
    *,
    to_email: str,
    first_name: str,
    last_name: str,
    set_password_url: str = "",
) -> bool:
    if (set_password_url or "").strip():
        return send_tippgeber_activated_with_password_email(
            to_email=to_email,
            first_name=first_name,
            last_name=last_name,
            set_password_url=set_password_url,
        )
    return send_tippgeber_activated_without_password_email(
        to_email=to_email,
        first_name=first_name,
        last_name=last_name,
    )


def send_client_deleted_email(*, to_email: str, first_name: str, last_name: str) -> bool:
    client_name = f"{first_name} {last_name}".strip()
    status = send_email_from_template(
        key=send_client_deleted_email.__name__,
        to_email=to_email,
        context={"client_name": client_name},
    )
    if status == EMAIL_TEMPLATE_SENT:
        return True
    if status == EMAIL_TEMPLATE_SEND_ERROR:
        raise EmailSendError(
            f"Template email send error: key={send_client_deleted_email.__name__} to={to_email}"
        )

    subject = "Bestätigung der Kontoschließung bei FleXXLager"
    body = (
        "Sehr geehrte/r Kunde/Kundin,\n\n"
        "Ihr Benutzerkonto bei FleXXLager wurde geschlossen.\n"
        "Ihre personenbezogenen Daten wurden vollständig aus unserem System gelöscht.\n\n"
        "Mit freundlichen Grüßen\n"
        "Ihr FleXXLager Team\n"
    )
    _, base_email = parseaddr(FROM_EMAIL)
    from_email = formataddr(("FleXXLager Team", base_email)) if base_email else FROM_EMAIL
    return _send_text(to_email=to_email, subject=subject, body=body, from_email=from_email)


def send_tippgeber_deleted_email(*, to_email: str, first_name: str, last_name: str) -> bool:
    tippgeber_name = f"{first_name} {last_name}".strip()
    status = send_email_from_template(
        key=send_tippgeber_deleted_email.__name__,
        to_email=to_email,
        context={"tippgeber_name": tippgeber_name},
    )
    if status == EMAIL_TEMPLATE_SENT:
        return True
    if status == EMAIL_TEMPLATE_SEND_ERROR:
        raise EmailSendError(
            f"Template email send error: key={send_tippgeber_deleted_email.__name__} to={to_email}"
        )

    subject = "Bestätigung der Kontoschließung bei FleXXLager"
    body = (
        "Sehr geehrte/r Tippgeber/in,\n\n"
        "Ihr Benutzerkonto bei FleXXLager wurde geschlossen.\n"
        "Ihre personenbezogenen Daten wurden vollständig aus unserem System gelöscht.\n\n"
        "Mit freundlichen Grüßen\n"
        "Ihr FleXXLager Team\n"
    )
    _, base_email = parseaddr(FROM_EMAIL)
    from_email = formataddr(("FleXXLager Team", base_email)) if base_email else FROM_EMAIL
    return _send_text(to_email=to_email, subject=subject, body=body, from_email=from_email)


# ---- password flows ----

def send_password_reset_email(*, to_email: str, first_name: str, last_name: str, reset_url: str) -> bool:
    status = send_email_from_template(
        key=send_password_reset_email.__name__,
        to_email=to_email,
        context={"link": reset_url},
    )
    if status == EMAIL_TEMPLATE_SENT:
        return True
    if status == EMAIL_TEMPLATE_SEND_ERROR:
        raise EmailSendError(
            f"Template email send error: key={send_password_reset_email.__name__} to={to_email}"
        )

    subject = "Passwortänderung bei FleXXLager"
    body = (
        "Sehr geehrte/r Nutzer/in,\n\n"
        "wir haben eine Anfrage zur Änderung Ihres Passworts erhalten.\n"
        "Bitte nutzen Sie den folgenden Link, um Ihr Passwort neu festzulegen:\n\n"
        f"{reset_url}\n\n"
        "Der Link ist 7 Tage gültig.\n"
        "Falls Sie keine Passwortänderung angefordert haben, können Sie diese E-Mail ignorieren und löschen.\n\n"
        "Mit freundlichen Grüßen\n"
        "Ihr FleXXLager Team\n"
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
    issue_date: date,
    issue_title: str,
) -> bool:
    issue_date_text = issue_date.strftime("%d.%m.%Y")
    tipgeber_client = (
        f"Kunde: {client_last_name} {client_first_name} {client_email}\n"
        f"Emission: {issue_date_text}: {issue_title}\n"
        f"Tippgeber: {tippgeber_last_name} {tippgeber_first_name} {tippgeber_email}"
    )
    status = send_email_from_template(
        key=send_tippgeber_added_interessent_email.__name__,
        to_email=NOTIFY_EMAIL,
        context={"tipgeber_client": tipgeber_client},
    )
    if status == EMAIL_TEMPLATE_SENT:
        return True
    if status == EMAIL_TEMPLATE_SEND_ERROR:
        raise EmailSendError(
            f"Template email send error: key={send_tippgeber_added_interessent_email.__name__} to={NOTIFY_EMAIL}"
        )

    subject = "Neuer Kunde durch Tippgeber – Aktivierung erforderlich"
    body = (
        "Guten Tag,\n\n"
        "ein Tippgeber hat einen neuen Kunden hinzugefügt:\n"
        f"{tipgeber_client}\n\n"
        "Bitte aktivieren Sie diesen Kunden, damit er eine Benachrichtigung erhält und sich im FleXXLager-System "
        "registrieren kann.\n\n"
        "Mit freundlichen Grüßen\n"
        "FleXXLager CRM\n"
    )
    _, base_email = parseaddr(FROM_EMAIL)
    from_email = formataddr(("FleXXLager CRM (Tippgeber)", base_email)) if base_email else FROM_EMAIL
    return _send_text(to_email=NOTIFY_EMAIL, subject=subject, body=body, from_email=from_email)


def send_tippgeber_link_conflict_email(
    *,
    tippgeber_email: str,
    tippgeber_first_name: str,
    tippgeber_last_name: str,
    client_email: str,
    client_first_name: str,
    client_last_name: str,
) -> bool:
    tipgeber_client = (
        f"Kunde: {client_last_name} {client_first_name} {client_email}\n"
        f"Tippgeber: {tippgeber_last_name} {tippgeber_first_name} {tippgeber_email}"
    )
    status = send_email_from_template(
        key=send_tippgeber_link_conflict_email.__name__,
        to_email=NOTIFY_EMAIL,
        context={"tipgeber_client": tipgeber_client},
    )
    if status == EMAIL_TEMPLATE_SENT:
        return True
    if status == EMAIL_TEMPLATE_SEND_ERROR:
        raise EmailSendError(
            f"Template email send error: key={send_tippgeber_link_conflict_email.__name__} to={NOTIFY_EMAIL}"
        )

    subject = "Zuordnung nicht erstellt – Kunde bereits vorhanden"
    body = (
        "Guten Tag,\n\n"
        "ein Tippgeber hat versucht, einen bereits bestehenden Kunden zuzuordnen. "
        "Die Zuordnung wurde nicht erstellt.\n\n"
        f"{tipgeber_client}\n\n"
        "Dieser Konflikt muss geklärt werden. Bitte setzen Sie sich mit dem Tippgeber in Verbindung.\n\n"
        "Mit freundlichen Grüßen\n"
        "FleXXLager CRM\n"
    )
    _, base_email = parseaddr(FROM_EMAIL)
    from_email = formataddr(("FleXXLager CRM (Tippgeber)", base_email)) if base_email else FROM_EMAIL
    return _send_text(to_email=NOTIFY_EMAIL, subject=subject, body=body, from_email=from_email)


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
    client_name = f"{first_name} {last_name}".strip()
    status = send_email_from_template(
        key=send_contract_signed_received_email.__name__,
        to_email=to_email,
        context={"client_name": client_name},
    )
    if status == EMAIL_TEMPLATE_SENT:
        return True
    if status == EMAIL_TEMPLATE_SEND_ERROR:
        raise EmailSendError(
            f"Template email send error: key={send_contract_signed_received_email.__name__} to={to_email}"
        )

    subject = "Ihr unterzeichneter Vertrag ist bei FleXXLager eingegangen"
    body = (
        f"Sehr geehrte/r {client_name},\n\n"
        "wir haben den von Ihnen unterzeichneten Vertrag per Post erhalten.\n"
        "Vielen Dank dafür!\n\n"
        "Mit freundlichen Grüßen\n"
        "Ihr FleXXLager Team\n"
    )
    _, base_email = parseaddr(FROM_EMAIL)
    from_email = formataddr(("FleXXLager Team", base_email)) if base_email else FROM_EMAIL
    return _send_text(to_email=to_email, subject=subject, body=body, from_email=from_email)


def send_contract_paid_received_email(
    *,
    to_email: str,
    first_name: str,
    last_name: str,
    contract_id: int,
    issue_title: str,
    paid_date: date,
    has_countersigned_contract: bool = False,
    attachments: Sequence[tuple[str, bytes, str]] | None = None,
) -> bool:
    full_name = f"{first_name} {last_name}".strip()
    template_key = (
        "send_contract_paid_received_email_with_countersigned_contract"
        if has_countersigned_contract
        else "send_contract_paid_received_email_without_countersigned_contract"
    )
    status = send_email_from_template(
        key=template_key,
        to_email=to_email,
        context={"full_name": full_name},
        attachments=attachments,
    )
    if status == EMAIL_TEMPLATE_SENT:
        return True
    if status == EMAIL_TEMPLATE_SEND_ERROR:
        raise EmailSendError(
            f"Template email send error: key={template_key} to={to_email}"
        )

    subject = "Zahlungseingang bei FleXXLager bestätigt"
    if has_countersigned_contract:
        body = (
            f"Sehr geehrte/r {full_name},\n\n"
            "Ihr Vertrag / Antrag auf Erwerb von Anleihen wurde von Ihnen bezahlt, und die Anleihen wurden Ihrem Konto gutgeschrieben.\n\n"
            "Bitte finden Sie den von uns gegengezeichneten Vertrag / Antrag im Anhang als zusätzliche Bestätigung.\n\n"
            "Mit freundlichen Grüßen\n"
            "Ihr FleXXLager Team\n"
        )
    else:
        body = (
            f"Sehr geehrte/r {full_name},\n\n"
            "Ihr Vertrag / Antrag auf Erwerb von Anleihen wurde von Ihnen bezahlt, und die Anleihen wurden Ihrem Konto gutgeschrieben.\n\n"
            "Der von uns unterzeichnete Vertrag / Antrag wurde Ihnen zudem per Post oder per E-Mail als weitere Bestätigung zugesandt.\n\n"
            "Mit freundlichen Grüßen\n"
            "Ihr FleXXLager Team\n"
        )
    _, base_email = parseaddr(FROM_EMAIL)
    from_email = formataddr(("FleXXLager Team", base_email)) if base_email else FROM_EMAIL
    return _send_text(
        to_email=to_email,
        subject=subject,
        body=body,
        from_email=from_email,
        attachments=attachments,
    )


# ---- Client self-service contract flow (notify internal) ----

def send_client_profile_completed_notify_email(
    *,
    client_email: str,
    first_name: str,
    last_name: str,
) -> bool:
    client_data = f"Kunde: {first_name} {last_name} {client_email}".strip()
    status = send_email_from_template(
        key=send_client_profile_completed_notify_email.__name__,
        to_email=NOTIFY_EMAIL,
        context={"client_data": client_data},
    )
    if status == EMAIL_TEMPLATE_SENT:
        return True
    if status == EMAIL_TEMPLATE_SEND_ERROR:
        raise EmailSendError(
            f"Template email send error: key={send_client_profile_completed_notify_email.__name__} to={NOTIFY_EMAIL}"
        )

    subject = "Profil vollständig ausgefüllt – Vertragsunterzeichnung möglich"
    body = (
        "Guten Tag,\n\n"
        "ein Kunde hat sein Profil vollständig ausgefüllt und kann nun den Vertrag unterzeichnen:\n\n"
        f"{client_data}\n\n"
        "Mit freundlichen Grüßen\n"
        "FleXXLager CRM\n"
    )
    _, base_email = parseaddr(FROM_EMAIL)
    from_email = formataddr(("FleXXLager CRM (Client)", base_email)) if base_email else FROM_EMAIL
    return _send_text(to_email=NOTIFY_EMAIL, subject=subject, body=body, from_email=from_email)


def send_client_password_set_notify_email(
    *,
    client_email: str,
    first_name: str,
    last_name: str,
) -> bool:
    client_data = f"Kunde: {first_name} {last_name} {client_email}".strip()
    status = send_email_from_template(
        key=send_client_password_set_notify_email.__name__,
        to_email=NOTIFY_EMAIL,
        context={"client_data": client_data},
    )
    if status == EMAIL_TEMPLATE_SENT:
        return True
    if status == EMAIL_TEMPLATE_SEND_ERROR:
        raise EmailSendError(
            f"Template email send error: key={send_client_password_set_notify_email.__name__} to={NOTIFY_EMAIL}"
        )

    subject = "Passwort durch Kunde gesetzt / geändert – Bitte prüfen"
    body = (
        "Guten Tag,\n\n"
        "ein Kunde hat sein Passwort gesetzt oder geändert:\n\n"
        f"{client_data}\n\n"
        "Mit freundlichen Grüßen\n"
        "FleXXLager CRM\n"
    )
    _, base_email = parseaddr(FROM_EMAIL)
    from_email = formataddr(("FleXXLager CRM (Client)", base_email)) if base_email else FROM_EMAIL
    return _send_text(to_email=NOTIFY_EMAIL, subject=subject, body=body, from_email=from_email)


def send_client_contract_created_notify_email(
    *,
    client_email: str,
    first_name: str,
    last_name: str,
    contract_id: int,
    issue_title: str,
) -> bool:
    client_contract = (
        f"Kunde: {first_name} {last_name} {client_email}\n"
        f"Vertrag: #{contract_id}\n"
        f"Emission: {issue_title}"
    )
    status = send_email_from_template(
        key=send_client_contract_created_notify_email.__name__,
        to_email=NOTIFY_EMAIL,
        context={"client_contract": client_contract},
    )
    if status == EMAIL_TEMPLATE_SENT:
        return True
    if status == EMAIL_TEMPLATE_SEND_ERROR:
        raise EmailSendError(
            f"Template email send error: key={send_client_contract_created_notify_email.__name__} to={NOTIFY_EMAIL}"
        )

    subject = "Neuer Vertrag durch Kunde – Bitte prüfen"
    body = (
        "Guten Tag,\n\n"
        "ein Kunde hat einen neuen Vertrag erstellt:\n\n"
        f"{client_contract}\n\n"
        "Bitte prüfen Sie den Vorgang im FleXXLager-System.\n\n"
        "Mit freundlichen Grüßen\n"
        "FleXXLager CRM\n"
    )
    _, base_email = parseaddr(FROM_EMAIL)
    from_email = formataddr(("FleXXLager CRM (Client)", base_email)) if base_email else FROM_EMAIL
    return _send_text(to_email=NOTIFY_EMAIL, subject=subject, body=body, from_email=from_email)


def send_client_contract_signed_notify_email(
    *,
    client_email: str,
    first_name: str,
    last_name: str,
    contract_id: int,
    issue_title: str,
) -> bool:
    client_contract = (
        f"Kunde: {first_name} {last_name} {client_email}\n"
        f"Vertrag: #{contract_id}\n"
        f"Emission: {issue_title}"
    )
    status = send_email_from_template(
        key=send_client_contract_signed_notify_email.__name__,
        to_email=NOTIFY_EMAIL,
        context={"client_contract": client_contract},
    )
    if status == EMAIL_TEMPLATE_SENT:
        return True
    if status == EMAIL_TEMPLATE_SEND_ERROR:
        raise EmailSendError(
            f"Template email send error: key={send_client_contract_signed_notify_email.__name__} to={NOTIFY_EMAIL}"
        )

    subject = "Vertrag durch Kunde unterzeichnet – Bitte prüfen"
    body = (
        "Guten Tag,\n\n"
        "ein Kunde hat einen Vertrag unterzeichnet:\n\n"
        f"{client_contract}\n\n"
        "Bitte prüfen Sie den Vorgang im FleXXLager-System.\n\n"
        "Mit freundlichen Grüßen\n"
        "FleXXLager CRM\n"
    )
    _, base_email = parseaddr(FROM_EMAIL)
    from_email = formataddr(("FleXXLager CRM (Client)", base_email)) if base_email else FROM_EMAIL
    return _send_text(to_email=NOTIFY_EMAIL, subject=subject, body=body, from_email=from_email)


def send_client_contract_created_email(
    *,
    to_email: str,
    first_name: str,
    last_name: str,
    file_decrs: str,
    attachments: Sequence[tuple[str, bytes, str]] | None = None,
) -> bool:
    full_name = f"{first_name} {last_name}".strip()
    status = send_email_from_template(
        key=send_client_contract_created_email.__name__,
        to_email=to_email,
        context={
            "full_name": full_name,
            "file_decrs": file_decrs,
        },
        attachments=attachments,
    )
    if status == EMAIL_TEMPLATE_SENT:
        return True
    if status == EMAIL_TEMPLATE_SEND_ERROR:
        raise EmailSendError(
            f"Template email send error: key={send_client_contract_created_email.__name__} to={to_email}"
        )

    subject = "Ihr Vertrag / Antrag auf Erwerb von Anleihen wurde erstellt"
    body = (
        f"Sehr geehrte/r {full_name},\n\n"
        "Ihr Vertrag / Antrag auf Erwerb von Anleihen wurde erstellt.\n"
        "Bitte finden Sie die folgenden Unterlagen im Anhang:\n\n"
        "* Vertrag / Antrag\n"
        f"{file_decrs}\n\n"
        "Sie können den Vertrag / Antrag ausdrucken, unterschreiben und uns die unterschriebene Version "
        "per E-Mail an service@flexxlager.com oder per Post an folgende Adresse senden:\n\n"
        "FleXXLager GmbH & Co. KG\n"
        "Weidenauer Straße 167\n"
        "57076 Siegen\n\n"
        "Alternativ können Sie den Vertrag / Antrag auch elektronisch auf unserer Website unter "
        "https://vertrag.flexxlager.de unterzeichnen.\n\n"
        "Nach Zahlungseingang und Verbuchung der Anleihen auf Ihrem Konto erhalten Sie den von uns "
        "gegengezeichneten Vertrag / Antrag per E-Mail als Bestätigung.\n\n"
        "Mit freundlichen Grüßen\n"
        "Ihr FleXXLager Team\n"
    )
    _, base_email = parseaddr(FROM_EMAIL)
    from_email = formataddr(("FleXXLager Team", base_email)) if base_email else FROM_EMAIL
    return _send_text(
        to_email=to_email,
        subject=subject,
        body=body,
        from_email=from_email,
        attachments=attachments,
    )


def send_client_contract_signed_email(
    *,
    to_email: str,
    first_name: str,
    last_name: str,
    file_decrs: str,
    attachments: Sequence[tuple[str, bytes, str]] | None = None,
) -> bool:
    full_name = f"{first_name} {last_name}".strip()
    status = send_email_from_template(
        key=send_client_contract_signed_email.__name__,
        to_email=to_email,
        context={
            "full_name": full_name,
            "file_decrs": file_decrs,
        },
        attachments=attachments,
    )
    if status == EMAIL_TEMPLATE_SENT:
        return True
    if status == EMAIL_TEMPLATE_SEND_ERROR:
        raise EmailSendError(
            f"Template email send error: key={send_client_contract_signed_email.__name__} to={to_email}"
        )

    subject = "Ihr Vertrag / Antrag auf Erwerb von Anleihen wurde von Ihnen unterzeichnet"
    body = (
        f"Sehr geehrte/r {full_name},\n\n"
        "Ihr Vertrag / Antrag auf Erwerb von Anleihen wurde von Ihnen unterzeichnet.\n"
        "Bitte finden Sie die folgenden Unterlagen im Anhang:\n\n"
        "* Vertrag / Antrag (von Ihnen unterzeichnet)\n"
        f"{file_decrs}\n\n"
        "Nach Zahlungseingang und Verbuchung der Anleihen auf Ihrem Konto erhalten Sie den von uns "
        "gegengezeichneten Vertrag / Antrag per E-Mail als Bestätigung.\n\n"
        "Mit freundlichen Grüßen\n"
        "Ihr FleXXLager Team\n"
    )
    _, base_email = parseaddr(FROM_EMAIL)
    from_email = formataddr(("FleXXLager Team", base_email)) if base_email else FROM_EMAIL
    return _send_text(
        to_email=to_email,
        subject=subject,
        body=body,
        from_email=from_email,
        attachments=attachments,
    )


def send_client_contract_deleted_notify_email(
    *,
    client_email: str,
    first_name: str,
    last_name: str,
    contract_id: int,
    issue_title: str,
) -> bool:
    client_contract = (
        f"Kunde: {first_name} {last_name} {client_email}\n"
        f"Vertrag: #{contract_id}\n"
        f"Emission: {issue_title}"
    )
    status = send_email_from_template(
        key=send_client_contract_deleted_notify_email.__name__,
        to_email=NOTIFY_EMAIL,
        context={"client_contract": client_contract},
    )
    if status == EMAIL_TEMPLATE_SENT:
        return True
    if status == EMAIL_TEMPLATE_SEND_ERROR:
        raise EmailSendError(
            f"Template email send error: key={send_client_contract_deleted_notify_email.__name__} to={NOTIFY_EMAIL}"
        )

    subject = "Vertrag durch Kunde gelöscht – Bitte prüfen"
    body = (
        "Guten Tag,\n\n"
        "ein Kunde hat einen Vertrag gelöscht:\n\n"
        f"{client_contract}\n\n"
        "Bitte prüfen Sie den Vorgang im FleXXLager-System.\n\n"
        "Mit freundlichen Grüßen\n"
        "FleXXLager CRM\n"
    )
    _, base_email = parseaddr(FROM_EMAIL)
    from_email = formataddr(("FleXXLager CRM (Client)", base_email)) if base_email else FROM_EMAIL
    return _send_text(to_email=NOTIFY_EMAIL, subject=subject, body=body, from_email=from_email)
