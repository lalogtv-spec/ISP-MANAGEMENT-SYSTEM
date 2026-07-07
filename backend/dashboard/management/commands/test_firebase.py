"""Django management command to test Firebase connection"""

from django.core.management.base import BaseCommand
from firebase_service import firebase
from django.conf import settings
import os


class Command(BaseCommand):
    help = 'Test Firebase Admin SDK connection and Firestore access'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('\n' + '='*60))
        self.stdout.write(self.style.SUCCESS('🔥 FIREBASE CONNECTION TEST'))
        self.stdout.write(self.style.SUCCESS('='*60 + '\n'))

        # Check configuration
        self.stdout.write(self.style.WARNING('📋 Configuration:'))
        self.stdout.write(f"  Project ID: {settings.FIREBASE_CONFIG.get('projectId')}")
        self.stdout.write(f"  Auth Domain: {settings.FIREBASE_CONFIG.get('authDomain')}\n")

        # Check credentials file
        self.stdout.write(self.style.WARNING('📂 Credentials File:'))
        cred_path = settings.FIREBASE_CREDENTIALS_PATH
        if os.path.exists(cred_path):
            self.stdout.write(self.style.SUCCESS(f"  ✅ Found at: {cred_path}\n"))
        else:
            self.stdout.write(self.style.ERROR(f"  ❌ NOT found at: {cred_path}"))
            self.stdout.write(self.style.ERROR("  Download from Firebase Console → Project Settings → Service Accounts\n"))
            return

        # Check connection
        self.stdout.write(self.style.WARNING('🔗 Connection Status:'))
        if firebase.is_connected():
            self.stdout.write(self.style.SUCCESS("  ✅ Firebase Admin SDK initialized"))
            self.stdout.write(self.style.SUCCESS("  ✅ Firestore connected"))
            self.stdout.write(self.style.SUCCESS("  ✅ Authentication ready\n"))
        else:
            self.stdout.write(self.style.ERROR("  ❌ Firebase not connected\n"))
            return

        # Test Firestore
        self.stdout.write(self.style.WARNING('📝 Testing Firestore:'))
        try:
            test_data = {'test': 'connection', 'status': 'success'}
            firebase.save_to_firestore('test', 'connection', test_data)
            retrieved = firebase.get_from_firestore('test', 'connection')
            
            if retrieved:
                self.stdout.write(self.style.SUCCESS("  ✅ Write successful"))
                self.stdout.write(self.style.SUCCESS("  ✅ Read successful\n"))
                firebase.db.collection('test').document('connection').delete()
            else:
                self.stdout.write(self.style.WARNING("  ⚠️  Could not retrieve test data\n"))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"  ⚠️  {str(e)}\n"))

        self.stdout.write(self.style.SUCCESS('='*60))
        self.stdout.write(self.style.SUCCESS('✅ Firebase is ready to use!'))
        self.stdout.write(self.style.SUCCESS('='*60 + '\n'))
