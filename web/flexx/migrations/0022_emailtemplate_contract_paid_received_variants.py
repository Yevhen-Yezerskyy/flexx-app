from django.db import migrations


BODY_TEXT_WITH_COUNTERSIGNED = (
    "Sehr geehrte/r {full_name},\n\n"
    "Ihr Vertrag / Antrag auf Erwerb von Anleihen wurde von Ihnen bezahlt, und die Anleihen wurden Ihrem Konto gutgeschrieben.\n\n"
    "Bitte finden Sie den von uns gegengezeichneten Vertrag / Antrag im Anhang als zusätzliche Bestätigung.\n\n"
    "Mit freundlichen Grüßen\n"
    "Ihr FleXXLager Team\n"
)


BODY_TEXT_WITHOUT_COUNTERSIGNED = (
    "Sehr geehrte/r {full_name},\n\n"
    "Ihr Vertrag / Antrag auf Erwerb von Anleihen wurde von Ihnen bezahlt, und die Anleihen wurden Ihrem Konto gutgeschrieben.\n\n"
    "Der von uns unterzeichnete Vertrag / Antrag wurde Ihnen zudem per Post oder per E-Mail als weitere Bestätigung zugesandt.\n\n"
    "Mit freundlichen Grüßen\n"
    "Ihr FleXXLager Team\n"
)


def create_or_update_templates(apps, schema_editor):
    EmailTemplate = apps.get_model("flexx", "EmailTemplate")
    common_defaults = {
        "from_role": "FleXXLager",
        "to_role": "Client",
        "from_text": "FleXXLager Team",
        "subject": "Zahlungseingang bei FleXXLager bestätigt",
        "placeholder": {
            "full_name": "{full_name}",
        },
        "is_active": True,
    }

    EmailTemplate.objects.update_or_create(
        key="send_contract_paid_received_email_with_countersigned_contract",
        defaults={
            **common_defaults,
            "body_text": BODY_TEXT_WITH_COUNTERSIGNED,
        },
    )
    EmailTemplate.objects.update_or_create(
        key="send_contract_paid_received_email_without_countersigned_contract",
        defaults={
            **common_defaults,
            "body_text": BODY_TEXT_WITHOUT_COUNTERSIGNED,
        },
    )


class Migration(migrations.Migration):

    dependencies = [
        ("flexx", "0021_fill_signed_received_at_for_client_signed_contracts"),
    ]

    operations = [
        migrations.RunPython(create_or_update_templates, migrations.RunPython.noop),
    ]
