import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

from django.db import connection
from face_auth.models import FaceProfile, FaceEnrollmentImage

print('Creating missing face_auth tables...')
with connection.schema_editor(atomic=True) as schema_editor:
    schema_editor.create_model(FaceProfile)
    schema_editor.create_model(FaceEnrollmentImage)

print('Tables created successfully.')
print('Checking model access...')
print(FaceProfile.objects.count())
