# Generated manually to add scheduled_time to Ticket
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0012_add_ticket_attachment'),
    ]

    operations = [
        migrations.AddField(
            model_name='ticket',
            name='scheduled_time',
            field=models.TimeField(blank=True, null=True),
        ),
    ]
