#!/usr/bin/env python
"""Update Firestore security rules using Firebase Admin SDK."""

import os
import sys
import json
from pathlib import Path

# Add the backend directory to the Python path
sys.path.insert(0, str(Path(__file__).parent))

# Set up Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from firebase_admin import firestore
from firebase_service import FirebaseService

def update_firestore_rules():
    """Update Firestore security rules to allow service account writes."""
    
    firebase = FirebaseService()
    
    if not firebase.is_connected():
        print("❌ Firebase not connected!")
        return False
    
    print("🔥 Updating Firestore Security Rules...")
    
    # The new rules that allow all read/write (for development)
    new_rules = """rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    match /{document=**} {
      allow read, write: if true;
    }
  }
}"""
    
    try:
        # The Firebase Admin SDK doesn't directly support updating rules via Python
        # Rules must be updated via Firebase Console, REST API, or CLI
        # This script demonstrates what rules should be deployed
        
        print("\n📋 New Firestore Security Rules:")
        print("=" * 60)
        print(new_rules)
        print("=" * 60)
        
        print("\n⚠️  To deploy these rules, use one of these methods:")
        print("\n1. Firebase Console (Manual):")
        print("   - Go to: https://console.firebase.google.com/project/ispmanagement-43a4c/firestore/rules")
        print("   - Click 'Edit Rules'")
        print("   - Replace all text with the rules above")
        print("   - Click 'Publish'")
        
        print("\n2. Firebase CLI (Recommended):")
        print("   - Install: npm install -g firebase-tools")
        print("   - Login: firebase login")
        print("   - Deploy: firebase deploy --only firestore:rules")
        
        print("\n3. REST API:")
        print("   - Use Firebase Admin SDK for Python with the rules REST endpoint")
        
        # Try alternative: use requests to update via REST API
        print("\n🔄 Attempting to update via REST API...")
        
        try:
            import requests
            from google.auth.transport.requests import Request
            from google.oauth2.service_account import Credentials
            
            # Get credentials from the service account JSON
            credentials_path = Path(__file__).parent / 'serviceAccountKey.json'
            
            if credentials_path.exists():
                with open(credentials_path) as f:
                    creds_json = json.load(f)
                
                project_id = creds_json.get('project_id')
                
                # Create credentials
                credentials = Credentials.from_service_account_file(
                    str(credentials_path),
                    scopes=['https://www.googleapis.com/auth/datastore']
                )
                
                # Refresh to get access token
                auth_request = Request()
                credentials.refresh(auth_request)
                
                # Prepare the rule update payload using Firebase Security Rules API
                url = f"https://firebasesecurityrules.googleapis.com/v1/projects/{project_id}/rulesets"
                
                # First, create a ruleset with the new rules
                create_payload = {
                    "source": {
                        "files": [
                            {
                                "name": "firestore.rules",
                                "content": new_rules
                            }
                        ]
                    }
                }
                
                print(f"🌐 Creating ruleset...")
                response = requests.post(url, json=create_payload, headers={"Authorization": f"Bearer {credentials.token}", "Content-Type": "application/json"})
                
                if response.status_code != 200 and response.status_code != 201:
                    print(f"❌ Failed to create ruleset: {response.status_code}")
                    print(f"   Response: {response.text}")
                    return False
                
                ruleset_data = response.json()
                ruleset_name = ruleset_data.get('name')
                
                print(f"✅ Ruleset created: {ruleset_name}")
                
                # Now, release the ruleset to Firestore
                release_url = f"https://firebasesecurityrules.googleapis.com/v1/projects/{project_id}/releases"
                release_payload = {
                    "name": f"projects/{project_id}/releases/cloud.firestore",
                    "rulesetName": ruleset_name
                }
                
                # Change to PUT method instead
                url = f"https://firebasesecurityrules.googleapis.com/v1/projects/{project_id}/releases/cloud.firestore"
                payload = {
                    "rulesetName": ruleset_name
                }
                
                headers = {
                    "Authorization": f"Bearer {credentials.token}",
                    "Content-Type": "application/json"
                }
                
                print(f"🌐 Releasing rules to Firestore...")
                
                response = requests.put(url, json=payload, headers=headers)
                
                if response.status_code == 200 or response.status_code == 201:
                    print("✅ Firestore security rules updated successfully!")
                    print(f"   Response: {response.json()}")
                    return True
                else:
                    print(f"❌ Failed to release rules: {response.status_code}")
                    print(f"   Response: {response.text}")
                    return False
                    
        except ImportError:
            print("   Note: Install 'google-auth' and 'requests' for REST API method")
            print("   pip install google-auth requests")
        except Exception as e:
            print(f"   REST API method failed: {e}")
        
        return False
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    success = update_firestore_rules()
    sys.exit(0 if success else 1)
