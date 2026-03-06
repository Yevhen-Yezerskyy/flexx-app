from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("flexx", "0027_delete_datenschutzeinwilligungtext"),
    ]

    operations = [
        migrations.AddField(
            model_name="contract",
            name="tippgeber_paid_at",
            field=models.DateField(blank=True, null=True),
        ),
    ]

