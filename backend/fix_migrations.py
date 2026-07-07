import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

from django.db import connection
cursor = connection.cursor()

# Delete the migration record for face_auth
print('Removing migration record for face_auth...')
cursor.execute("DELETE FROM django_migrations WHERE app='face_auth'")
print('Deleted migration record')

# Now reapply migrations
from django.core.management import call_command
print('\nReapplying migrations for face_auth...')
call_command('migrate', 'face_auth', verbosity=2)
print('\nDone! Checking if table now exists...')

# Verify table exists
try:
    cursor.execute('SELECT 1 FROM face_auth_faceprofile LIMIT 1')
    print('✓ face_auth_faceprofile table NOW EXISTS!')
except Exception as e:
    print(f'✗ Table still does not exist: {e}')
