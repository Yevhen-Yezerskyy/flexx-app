from django.db import migrations, models


def copy_placeholder_to_json(apps, schema_editor):
    EmailTemplate = apps.get_model("flexx", "EmailTemplate")
    for template in EmailTemplate.objects.all():
        value = template.placeholder
        if isinstance(value, dict):
            template.placeholder_json = value
        else:
            text = "" if value is None else str(value).strip()
            template.placeholder_json = {"name": text} if text else {}
        template.save(update_fields=["placeholder_json"])


class Migration(migrations.Migration):

    dependencies = [
        ("flexx", "0015_contract_date_nullable"),
    ]

    operations = [
        migrations.AddField(
            model_name="emailtemplate",
            name="placeholder_json",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.RunPython(copy_placeholder_to_json, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="emailtemplate",
            name="placeholder",
        ),
        migrations.RenameField(
            model_name="emailtemplate",
            old_name="placeholder_json",
            new_name="placeholder",
        ),
    ]
