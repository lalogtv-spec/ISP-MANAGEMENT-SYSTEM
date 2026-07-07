from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('security', '0002_add_sensitive_actions_flag'),
    ]

    operations = [
        migrations.AlterField(
            model_name='biometricdata',
            name='user',
            field=models.ForeignKey(on_delete=models.CASCADE, related_name='biometric_data', to='auth.user'),
        ),
    ]
