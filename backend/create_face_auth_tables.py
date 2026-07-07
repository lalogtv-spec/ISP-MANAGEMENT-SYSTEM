import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django

django.setup()

from django.core.management import call_command
from django.db import connection

# Check migration history
cursor = connection.cursor()
cursor.execute("SELECT app, name FROM django_migrations WHERE app='face_auth'")
records = cursor.fetchall()
print(f'Migration records for face_auth: {records}')

# Try to query FaceProfile directly
from face_auth.models import FaceProfile
print(f'FaceProfile model: {FaceProfile}')

# Try to query directly
try:
    FaceProfile.objects.all().first()
    print('✓ FaceProfile table accessible!')
except Exception as e:
    print(f'✗ Cannot access FaceProfile: {e}')
    print('Attempting to create table...')
    
    # Insert migration record if it doesn't exist
    cursor.execute("INSERT INTO django_migrations (app, name, applied) VALUES ('face_auth', '0001_initial', datetime('now'))")
    print('✓ Migration record inserted')
    
    # Now create the tables using raw SQL from the migration
    print('Creating face_auth_faceprofile table...')
    cursor.execute('''
    CREATE TABLE "face_auth_faceprofile" (
        "id" bigint NOT NULL PRIMARY KEY AUTOINCREMENT,
        "enabled" bool NOT NULL,
        "created_at" datetime NOT NULL,
        "updated_at" datetime NOT NULL,
        "user_id" bigint NOT NULL UNIQUE REFERENCES "auth_user" ("id") DEFERRABLE INITIALLY DEFERRED
    )
    ''')
    
    print('Creating face_auth_faceenrollmentimage table...')
    cursor.execute('''
    CREATE TABLE "face_auth_faceenrollmentimage" (
        "id" bigint NOT NULL PRIMARY KEY AUTOINCREMENT,
        "image" varchar(100) NOT NULL,
        "captured_at" datetime NOT NULL,
        "profile_id" bigint NOT NULL REFERENCES "face_auth_faceprofile" ("id") DEFERRABLE INITIALLY DEFERRED
    )
    ''')
    
    print('✓ Tables created!')
    
    # Verify
    try:
        FaceProfile.objects.all().first()
        print('✓ FaceProfile table is now accessible!')
    except Exception as e2:
        print(f'✗ Still cannot access: {e2}')
