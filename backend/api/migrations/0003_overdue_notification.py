# Generated migration for OverdueNotification model

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0002_application_user'),
    ]

    operations = [
        migrations.CreateModel(
            name='OverdueNotification',
            fields=[
                ('notification_id', models.CharField(max_length=20, primary_key=True, serialize=False, unique=True)),
                ('client', models.CharField(max_length=255)),
                ('notification_type', models.CharField(choices=[('First Notice', 'First Notice (Day 0-1)'), ('Second Notice', 'Second Notice (Day 2-3)'), ('Disconnection Warning', 'Disconnection Warning (Day 4+)')], max_length=50)),
                ('status', models.CharField(choices=[('Pending', 'Pending'), ('Sent', 'Sent'), ('Failed', 'Failed')], default='Pending', max_length=20)),
                ('email_sent', models.BooleanField(default=False)),
                ('sms_sent', models.BooleanField(default=False)),
                ('email_response', models.TextField(blank=True, null=True)),
                ('sms_response', models.TextField(blank=True, null=True)),
                ('amount_due', models.DecimalField(decimal_places=2, max_digits=10)),
                ('days_overdue', models.IntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('sent_at', models.DateTimeField(blank=True, null=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]
