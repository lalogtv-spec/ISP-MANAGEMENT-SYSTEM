#!/usr/bin/env python
"""Check current Firestore security rules."""

import os
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from firebase_service import FirebaseService
from google.cloud import firebaserules_v1
from google.oauth2 import service_account

def check_firestore_rules():
    """Check current Firestore security rules."""
    
    print("🔍 Checking Firestore Security Rules...")
    
    try:
        credentials_path = Path(__file__).parent / 'serviceAccountKey.json'
        
        with open(credentials_path) as f:
            creds_json = json.load(f)
        
        project_id = creds_json.get('project_id')
        
        # Create credentials
        credentials = service_account.Credentials.from_service_account_file(
            str(credentials_path),
            scopes=['https://www.googleapis.com/auth/cloud-platform']
        )
        
        # Create the Firestore Rules API client
        client = firebaserules_v1.FirebaseRulesClient(credentials=credentials)
        
        project_name = f'projects/{project_id}'
        
        # Get the current release
        try:
            release_name = f'{project_name}/releases/cloud.firestore'
            request = firebaserules_v1.GetReleaseRequest(name=release_name)
            release = client.get_release(request=request)
            
            print(f"✅ Current Release: {release.name}")
            print(f"   Ruleset: {release.ruleset_name}")
            
            # Get the ruleset
            ruleset = client.get_ruleset(request=firebaserules_v1.GetRulesetRequest(name=release.ruleset_name))
            
            print(f"\n📋 Current Rules:")
            print("=" * 60)
            if ruleset.source.files:
                for file in ruleset.source.files:
                    print(file.content)
            else:
                print("(No files found)")
            print("=" * 60)
            
        except Exception as e:
            print(f"Error fetching release: {e}")
            
        return True
        
    except ImportError:
        print("❌ google-cloud-firebaserules not installed")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    check_firestore_rules()
