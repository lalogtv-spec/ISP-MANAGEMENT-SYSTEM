import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

from django.db import connection
cursor = connection.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS face_auth_faceenrollmentimage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    image VARCHAR(100) NOT NULL,
    captured_at DATETIME NOT NULL,
    profile_id BIGINT NOT NULL REFERENCES face_auth_faceprofile(id) DEFERRABLE INITIALLY DEFERRED
)
""")
print('Created face_auth_faceenrollmentimage table if missing.')
