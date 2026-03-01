from django.db import migrations
from django.utils import timezone


def fill_signed_received_at(apps, schema_editor):
    Contract = apps.get_model("flexx", "Contract")
    today = timezone.localdate()
    (
        Contract.objects
        .filter(contract_pdf_signed__gt="")
        .filter(signed_received_at__isnull=True)
        .update(signed_received_at=today)
    )


class Migration(migrations.Migration):

    dependencies = [
        ("flexx", "0020_emailtemplate_client_password_set_notify_email"),
    ]

    operations = [
        migrations.RunPython(fill_signed_received_at, migrations.RunPython.noop),
    ]
