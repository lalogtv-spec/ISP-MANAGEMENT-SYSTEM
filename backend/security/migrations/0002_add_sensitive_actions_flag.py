from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('security', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='mfasettings',
            name='require_biometric_for_sensitive_actions',
            field=models.BooleanField(default=False),
        ),
    ]
