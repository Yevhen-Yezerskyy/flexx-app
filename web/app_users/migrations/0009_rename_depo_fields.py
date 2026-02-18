from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("app_users", "0008_flexxuser_mobile_phone"),
    ]

    operations = [
        migrations.RenameField(
            model_name="flexxuser",
            old_name="bank_depo_iban",
            new_name="bank_depo_depotnummer",
        ),
        migrations.RenameField(
            model_name="flexxuser",
            old_name="bank_depo_bic",
            new_name="bank_depo_blz",
        ),
    ]

