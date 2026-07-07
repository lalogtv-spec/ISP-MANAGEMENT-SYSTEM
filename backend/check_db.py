import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

from django.db import connection
cursor = connection.cursor()

# Check if table exists
try:
    cursor.execute('SELECT 1 FROM face_auth_faceprofile LIMIT 1')
    print('✓ face_auth_faceprofile table EXISTS')
except Exception as e:
    print(f'✗ face_auth_faceprofile table DOES NOT EXIST: {e}')

# List all tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
print(f'\nTotal tables in database: {len(tables)}')
face_auth_tables = [t[0] for t in tables if 'face' in t[0].lower()]
print(f'Face auth tables: {face_auth_tables}')

# If table doesn't exist, try to create it
if not face_auth_tables:
    print('\nAttempting to fix by flushing and re-migrating...')
    from django.core.management import call_command
    call_command('makemigrations')
    call_command('migrate', verbosity=2)
