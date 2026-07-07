# Generated migration for NotificationSettings model

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0003_overdue_notification'),
    ]

    operations = [
        migrations.CreateModel(
            name='NotificationSettings',
            fields=[
                ('client_id', models.CharField(max_length=10, primary_key=True, serialize=False, unique=True)),
                ('client_name', models.CharField(max_length=255)),
                ('email', models.EmailField(max_length=254)),
                ('phone', models.CharField(max_length=20)),
                ('notifications_enabled', models.BooleanField(default=True, help_text='Enable/disable all notifications')),
                ('notification_method', models.CharField(choices=[('email', 'Email Only'), ('sms', 'SMS Only'), ('both', 'Email & SMS')], default='both', max_length=10)),
                ('grace_period_days', models.IntegerField(default=3, help_text='Days before disconnection after due date')),
                ('send_first_notice', models.BooleanField(default=True, help_text='Send notice on day 1-2 of being overdue')),
                ('send_second_notice', models.BooleanField(default=True, help_text='Send urgent notice on day 3')),
                ('send_disconnection_warning', models.BooleanField(default=True, help_text='Send final warning after day 3')),
                ('auto_disconnect_enabled', models.BooleanField(default=True, help_text='Automatically disconnect after grace period')),
                ('allow_email_reminders', models.BooleanField(default=True)),
                ('allow_sms_reminders', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Notification Settings',
                'verbose_name_plural': 'Notification Settings',
            },
        ),
    ]
