from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('security', '0005_fix_biometric_onetoone'),
    ]

    operations = [
        migrations.AddField(
            model_name='usersecurityprofile',
            name='phone_number',
            field=models.CharField(blank=True, default='', max_length=20),
        ),
    ]
