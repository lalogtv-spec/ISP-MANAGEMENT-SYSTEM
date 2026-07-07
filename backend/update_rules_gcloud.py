#!/usr/bin/env python
"""Update Firestore security rules using Google Cloud Python client."""

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

from google.cloud import firebaserules_v1
from google.auth.transport.grpc import secure_authorized_channel
from google.oauth2 import service_account

def update_firestore_rules():
    """Update Firestore security rules using Google Cloud API."""
    
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
        # Load service account credentials
        credentials_path = Path(__file__).parent / 'serviceAccountKey.json'
        
        if not credentials_path.exists():
            print(f"❌ Service account key not found: {credentials_path}")
            return False
        
        # Read project ID from service account
        with open(credentials_path) as f:
            creds_json = json.load(f)
        
        project_id = creds_json.get('project_id')
        
        print(f"📝 Project ID: {project_id}")
        
        # Create credentials from service account
        credentials = service_account.Credentials.from_service_account_file(
            str(credentials_path),
            scopes=['https://www.googleapis.com/auth/cloud-platform']
        )
        
        # Create the Firestore Rules API client
        client = firebaserules_v1.FirebaseRulesClient(credentials=credentials)
        
        print(f"🌐 Creating ruleset...")
        
        # Create a ruleset
        ruleset = firebaserules_v1.Ruleset()
        ruleset.source.files.append(
            firebaserules_v1.File(
                name='firestore.rules',
                content=new_rules
            )
        )
        
        project_name = f'projects/{project_id}'
        
        # Create the ruleset
        try:
            result = client.create_ruleset(
                name=project_name,
                ruleset=ruleset
            )
            ruleset_name = result.name
            print(f"✅ Ruleset created: {ruleset_name}")
            
            # Now release the ruleset
            print(f"🚀 Releasing ruleset to Firestore...")
            
            release = firebaserules_v1.Release()
            release.ruleset_name = ruleset_name
            release.name = f'{project_name}/releases/cloud.firestore'
            
            release_result = client.update_release(
                name=release.name,
                release=release
            )
            
            print("✅ Firestore security rules updated successfully!")
            print(f"   Release: {release_result.name}")
            return True
            
        except Exception as e:
            print(f"❌ Error updating rules: {e}")
            print(f"   This may require additional Google Cloud permissions.")
            return False
            
    except ImportError:
        print("❌ google-cloud-firebaserules not installed")
        print("   Install with: pip install google-cloud-firebaserules")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = update_firestore_rules()
    sys.exit(0 if success else 1)
