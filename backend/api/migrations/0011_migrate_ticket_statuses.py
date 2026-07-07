"""
Data migration to normalize Ticket.status values and add Scheduled status handling.

Converts:
 - 'Open' -> 'Pending'
 - 'Closed' -> 'Resolved'

This is a reversible noop for safety (reverse does nothing).
"""
from django.db import migrations


def forwards(apps, schema_editor):
    Ticket = apps.get_model('api', 'Ticket')
    # Normalize legacy statuses
    Ticket.objects.filter(status='Open').update(status='Pending')
    Ticket.objects.filter(status='Closed').update(status='Resolved')


def reverse(apps, schema_editor):
    # Intentionally left as noop to avoid destructive reversions
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0010_alter_activitylog_activity_type_and_more'),
    ]

    operations = [
        migrations.RunPython(forwards, reverse_code=migrations.RunPython.noop),
    ]
