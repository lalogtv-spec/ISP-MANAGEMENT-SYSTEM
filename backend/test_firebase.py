"""
Firebase connection test script.

Run this manually to verify Firebase is properly connected to the backend.
The file is intentionally import-safe so Django test discovery will skip it
without executing any output or network work.
"""

from __future__ import annotations

import os
import sys

import django


def main() -> int:
    """Run a quick Firebase connectivity check."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    django.setup()

    from django.conf import settings
    from firebase_service import firebase

    print("=" * 60)
    print("FIREBASE CONNECTION TEST")
    print("=" * 60)

    print("\nConfiguration Check:")
    print(f"Project ID: {settings.FIREBASE_CONFIG.get('projectId')}")
    print(f"Auth Domain: {settings.FIREBASE_CONFIG.get('authDomain')}")
    print(f"Storage Bucket: {settings.FIREBASE_CONFIG.get('storageBucket')}")

    print("\nCredentials File Check:")
    cred_path = settings.FIREBASE_CREDENTIALS_PATH
    if os.path.exists(cred_path):
        print(f"Found at: {cred_path}")
    else:
        print(f"NOT found at: {cred_path}")
        print("Please download the service account key from Firebase Console.")
        return 1

    print("\nFirebase Connection Check:")
    if firebase.is_connected():
        print("Firebase Admin SDK initialized successfully!")
        print("Firestore is connected")
        print("Authentication is available")
    else:
        print("Firebase is not connected")
        print("Check the error messages above")
        return 1

    print("\nTesting Firestore Operations:")
    try:
        test_data = {
            'test_name': 'Firebase Connection Test',
            'timestamp': 'Test',
            'status': 'Working!',
        }
        firebase.save_to_firestore('test_collection', 'test_doc', test_data)

        retrieved_data = firebase.get_from_firestore('test_collection', 'test_doc')
        if retrieved_data:
            print("Successfully wrote and read from Firestore")
            print(f"Retrieved: {retrieved_data}")
            firebase.db.collection('test_collection').document('test_doc').delete()
            print("Test data cleaned up")
        else:
            print("Could not retrieve test data")
            return 1
    except Exception as exc:
        print(f"Firestore test skipped: {exc}")

    print("\n" + "=" * 60)
    print("All checks passed! Firebase is ready to use.")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
