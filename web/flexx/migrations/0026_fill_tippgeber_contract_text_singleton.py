from django.db import migrations


def create_single_tippgeber_contract_text(apps, schema_editor):
    model = apps.get_model("flexx", "TippgeberContractText")
    model.objects.get_or_create(id=1, defaults={"text": ""})


def noop_reverse(apps, schema_editor):
    return


class Migration(migrations.Migration):
    dependencies = [
        ("flexx", "0025_tippgebercontracttext_tippgebercontract"),
    ]

    operations = [
        migrations.RunPython(create_single_tippgeber_contract_text, noop_reverse),
    ]
