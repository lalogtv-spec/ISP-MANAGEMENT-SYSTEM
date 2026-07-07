from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('security', '0006_usersecurityprofile_phone_number'),
    ]

    operations = [
        migrations.AddField(
            model_name='mfasettings',
            name='allow_otp_login',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='mfasettings',
            name='allow_facial_login',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='mfasettings',
            name='allow_fingerprint_login',
            field=models.BooleanField(default=True),
        ),
    ]
