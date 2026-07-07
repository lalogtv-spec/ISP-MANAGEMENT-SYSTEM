from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('security', '0007_mfasettings_login_factor_toggles'),
    ]

    operations = [
        migrations.AddField(
            model_name='biometricdata',
            name='sample_image_path',
            field=models.CharField(blank=True, default='', max_length=500),
        ),
    ]
