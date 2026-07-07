from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    initial = False

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='PaymentMethod',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('display_name', models.CharField(max_length=100)),
                ('detail', models.CharField(blank=True, max_length=255)),
                ('brand', models.CharField(blank=True, max_length=50)),
                ('verified', models.BooleanField(default=False)),
                ('default', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('client', models.ForeignKey(on_delete=models.deletion.CASCADE, to='api.client')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]
