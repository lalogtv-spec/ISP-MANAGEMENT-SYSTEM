# Generated migration for SMS and Email notification log models

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0004_notification_settings'),
    ]

    operations = [
        migrations.CreateModel(
            name='SMSNotificationLog',
            fields=[
                ('sms_id', models.CharField(max_length=20, primary_key=True, serialize=False, unique=True)),
                ('client_id', models.CharField(max_length=10)),
                ('customer_name', models.CharField(max_length=255)),
                ('mobile_number', models.CharField(max_length=20)),
                ('notification_type', models.CharField(choices=[('Overdue Notice', 'Overdue Notice'), ('Final Warning', 'Final Warning'), ('Disconnection Notice', 'Disconnection Notice'), ('Payment Reminder', 'Payment Reminder')], max_length=50)),
                ('message_content', models.TextField()),
                ('amount_due', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ('status', models.CharField(choices=[('Simulated Sent', 'Simulated Sent'), ('Pending', 'Pending'), ('Failed', 'Failed')], default='Simulated Sent', max_length=50)),
                ('sent_at', models.DateTimeField(auto_now_add=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'SMS Notification Log',
                'verbose_name_plural': 'SMS Notification Logs',
                'ordering': ['-sent_at'],
            },
        ),
        migrations.CreateModel(
            name='EmailNotificationLog',
            fields=[
                ('email_id', models.CharField(max_length=20, primary_key=True, serialize=False, unique=True)),
                ('client_id', models.CharField(max_length=10)),
                ('customer_name', models.CharField(max_length=255)),
                ('email_address', models.EmailField(max_length=254)),
                ('notification_type', models.CharField(choices=[('Overdue Notice', 'Overdue Notice'), ('Final Warning', 'Final Warning'), ('Disconnection Notice', 'Disconnection Notice'), ('Payment Reminder', 'Payment Reminder')], max_length=50)),
                ('subject', models.CharField(max_length=255)),
                ('message_content', models.TextField()),
                ('amount_due', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ('status', models.CharField(choices=[('Simulated Sent', 'Simulated Sent'), ('Pending', 'Pending'), ('Failed', 'Failed')], default='Simulated Sent', max_length=50)),
                ('sent_at', models.DateTimeField(auto_now_add=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Email Notification Log',
                'verbose_name_plural': 'Email Notification Logs',
                'ordering': ['-sent_at'],
            },
        ),
    ]
