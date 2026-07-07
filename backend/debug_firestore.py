#!/usr/bin/env python
"""Detailed Firestore permission debugging."""

import os
import sys
import json
from pathlib import Path
import time

sys.path.insert(0, str(Path(__file__).parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from firebase_service import FirebaseService
from firebase_admin import firestore

def debug_firestore_permissions():
    """Debug Firestore permissions in detail."""
    
    print("🔍 Detailed Firestore Permission Debug")
    print("=" * 60)
    
    firebase = FirebaseService()
    
    if not firebase.is_connected():
        print("❌ Firebase not connected!")
        return False
    
    print("✅ Firebase connected")
    print(f"   Database: {firebase.db}")
    
    try:
        # Get database info
        db = firebase.db
        
        # Try a simple write operation with detailed error handling
        print("\n📝 Attempting to write test document...")
        
        test_ref = db.collection('_debug_test').document('test_doc')
        
        try:
            test_ref.set({
                'timestamp': firestore.SERVER_TIMESTAMP,
                'test': True,
                'message': 'This is a test document'
            })
            
            print("✅ Write successful!")
            
            # Clean up
            test_ref.delete()
            print("✅ Cleanup successful!")
            
            return True
            
        except Exception as write_error:
            print(f"❌ Write failed: {write_error}")
            print(f"\n   Error type: {type(write_error).__name__}")
            print(f"   Error details: {str(write_error)}")
            
            # More detailed error inspection
            if hasattr(write_error, 'details'):
                print(f"   Details: {write_error.details()}")
            
            if hasattr(write_error, 'code'):
                print(f"   Code: {write_error.code()}")
            
            # Possible causes
            print("\n🔍 Possible causes:")
            print("   1. Firestore security rules deny writes from service account")
            print("   2. Service account lacks project-level permissions")
            print("   3. Firestore API not enabled in Google Cloud")
            print("   4. Database not fully initialized (may take a few minutes)")
            
            print("\n💡 Solutions:")
            print("   A. Check Firestore rules are published with:")
            print("      rules_version = '2';")
            print("      service cloud.firestore {")
            print("        match /databases/{database}/documents {")
            print("          match /{document=**} {")
            print("            allow read, write: if true;")
            print("          }")
            print("        }")
            print("      }")
            print("   B. Wait 30-60 seconds after publishing rules")
            print("   C. Restart Django: python manage.py runserver")
            
            return False
    
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    debug_firestore_permissions()
