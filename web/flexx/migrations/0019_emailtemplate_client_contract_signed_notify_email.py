from django.db import migrations


BODY_TEXT = (
    "Guten Tag,\n\n"
    "ein Kunde hat einen Vertrag unterzeichnet:\n\n"
    "{client_contract}\n\n"
    "Bitte prüfen Sie den Vorgang im FleXXLager-System.\n\n"
    "Mit freundlichen Grüßen\n"
    "FleXXLager CRM\n"
)


def create_or_update_template(apps, schema_editor):
    EmailTemplate = apps.get_model("flexx", "EmailTemplate")
    EmailTemplate.objects.update_or_create(
        key="send_client_contract_signed_notify_email",
        defaults={
            "from_role": "Client",
            "to_role": "FleXXLager",
            "from_text": "FleXXLager CRM (Client)",
            "subject": "Vertrag durch Kunde unterzeichnet – Bitte prüfen",
            "body_text": BODY_TEXT,
            "placeholder": {
                "client_contract": "{client_contract}",
            },
            "is_active": True,
        },
    )


class Migration(migrations.Migration):

    dependencies = [
        ("flexx", "0018_emailtemplate_client_contract_signed_email"),
    ]

    operations = [
        migrations.RunPython(create_or_update_template, migrations.RunPython.noop),
    ]
