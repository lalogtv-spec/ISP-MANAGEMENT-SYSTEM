from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('security', '0003_alter_biometricdata_user'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='biometricdata',
            unique_together=set(),
        ),
        migrations.AlterField(
            model_name='biometricdata',
            name='template_hash',
            field=models.CharField(db_index=True, max_length=255),
        ),
    ]
