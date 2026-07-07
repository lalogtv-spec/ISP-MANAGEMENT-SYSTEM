from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0015_merge_0011_migrate_ticket_statuses_0014_unique_client_email'),
    ]

    operations = [
        migrations.CreateModel(
            name='ApplicationDecision',
            fields=[
                ('app_id', models.CharField(max_length=10, primary_key=True, serialize=False, unique=True)),
                ('name', models.CharField(max_length=255)),
                ('phone', models.CharField(max_length=20)),
                ('email', models.EmailField(max_length=254)),
                ('address', models.TextField()),
                ('plan', models.CharField(max_length=100)),
                ('status', models.CharField(choices=[('Approved', 'Approved'), ('Declined', 'Declined')], max_length=20)),
                ('reason', models.TextField(blank=True, default='')),
                ('date', models.DateField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='auth.user')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]
