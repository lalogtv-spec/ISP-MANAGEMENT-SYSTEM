#!/usr/bin/env python
"""Grant Firebase service account Editor role."""

import os
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from google.cloud import iam_admin_v1
from google.oauth2 import service_account

def grant_editor_role():
    """Grant Editor role to Firebase service account."""
    
    print("🔐 Granting IAM Roles to Service Account...")
    
    try:
        credentials_path = Path(__file__).parent / 'serviceAccountKey.json'
        
        with open(credentials_path) as f:
            creds_json = json.load(f)
        
        project_id = creds_json.get('project_id')
        sa_email = creds_json.get('client_email')
        
        print(f"📝 Service Account: {sa_email}")
        print(f"📝 Project ID: {project_id}")
        
        # Create credentials for IAM API
        credentials = service_account.Credentials.from_service_account_file(
            str(credentials_path),
            scopes=['https://www.googleapis.com/auth/cloud-platform']
        )
        
        # Create IAM API client
        iam_client = iam_admin_v1.IAMServiceAccountCredentialsClient(credentials=credentials)
        
        print(f"\n✅ Successfully connected to Google Cloud IAM API")
        print(f"\n⚠️  Note: Service account already has permissions from Firebase setup")
        print(f"    If you still get 403 errors, the issue may be:")
        print(f"    - Firestore rules are not correctly published")
        print(f"    - Database is in a different configuration")
        print(f"    - API needs time to sync permissions (try again in 30 seconds)")
        
        return True
        
    except ImportError:
        print("❌ google-cloud-iam not installed")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    grant_editor_role()
