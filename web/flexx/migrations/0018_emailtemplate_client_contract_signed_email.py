from django.db import migrations


BODY_TEXT = (
    "Sehr geehrte/r {full_name},\n\n"
    "Ihr Vertrag / Antrag auf Erwerb von Anleihen wurde von Ihnen unterzeichnet.\n"
    "Bitte finden Sie die folgenden Unterlagen im Anhang:\n\n"
    "* Vertrag / Antrag (von Ihnen unterzeichnet)\n"
    "{file_decrs}\n\n"
    "Nach Zahlungseingang und Verbuchung der Anleihen auf Ihrem Konto erhalten Sie den von uns "
    "gegengezeichneten Vertrag / Antrag per E-Mail als Bestätigung.\n\n"
    "Mit freundlichen Grüßen\n"
    "Ihr FleXXLager Team\n"
)


def create_or_update_template(apps, schema_editor):
    EmailTemplate = apps.get_model("flexx", "EmailTemplate")
    EmailTemplate.objects.update_or_create(
        key="send_client_contract_signed_email",
        defaults={
            "from_role": "FleXXLager",
            "to_role": "Client",
            "from_text": "FleXXLager Team",
            "subject": "Ihr Vertrag / Antrag auf Erwerb von Anleihen wurde von Ihnen unterzeichnet",
            "body_text": BODY_TEXT,
            "placeholder": {
                "full_name": "{full_name}",
                "file_decrs": "{file_decrs}",
            },
            "is_active": True,
        },
    )


class Migration(migrations.Migration):

    dependencies = [
        ("flexx", "0017_emailtemplate_client_contract_created_email"),
    ]

    operations = [
        migrations.RunPython(create_or_update_template, migrations.RunPython.noop),
    ]
