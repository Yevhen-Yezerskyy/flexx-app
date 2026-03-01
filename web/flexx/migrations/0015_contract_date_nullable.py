from django.db import migrations, models


def clear_contract_dates(apps, schema_editor):
    Contract = apps.get_model("flexx", "Contract")
    Contract.objects.exclude(contract_date=None).update(contract_date=None)


class Migration(migrations.Migration):

    dependencies = [
        ("flexx", "0014_client_role_requires_contract"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="contract",
            options={"ordering": ["-id"]},
        ),
        migrations.AlterField(
            model_name="contract",
            name="contract_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.RunPython(clear_contract_dates, migrations.RunPython.noop),
    ]
