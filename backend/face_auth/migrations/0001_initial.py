from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.CreateModel(
            name='FaceProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('enabled', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='face_profile', to='auth.user')),
            ],
            options={
                'verbose_name': 'Face Profile',
                'verbose_name_plural': 'Face Profiles',
            },
        ),
        migrations.CreateModel(
            name='FaceEnrollmentImage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('image', models.ImageField(upload_to='face_db/%Y/%m/%d/')),
                ('captured_at', models.DateTimeField(auto_now_add=True)),
                ('profile', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='enrollment_images', to='face_auth.faceprofile')),
            ],
            options={
                'verbose_name': 'Face Enrollment Image',
                'verbose_name_plural': 'Face Enrollment Images',
            },
        ),
    ]
