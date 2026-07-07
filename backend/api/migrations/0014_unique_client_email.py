from django.db import migrations, models


def remove_duplicate_client_emails(apps, schema_editor):
    Client = apps.get_model('api', 'Client')
    seen_emails = {}
    duplicates = []

    for client in Client.objects.all().order_by('email', 'client_id').iterator():
        email = (client.email or '').strip().lower()
        if not email:
            continue
        if email in seen_emails:
            duplicates.append(client.pk)
        else:
            seen_emails[email] = client.pk

    if duplicates:
        Client.objects.filter(pk__in=duplicates).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0013_add_scheduled_time_to_ticket'),
    ]

    operations = [
        migrations.RunPython(remove_duplicate_client_emails, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='client',
            name='email',
            field=models.EmailField(unique=True),
        ),
    ]
