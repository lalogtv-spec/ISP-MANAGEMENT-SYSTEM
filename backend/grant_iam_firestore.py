#!/usr/bin/env python
"""Update Google Cloud IAM to grant Firestore Editor role to service account."""

import os
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from google.cloud import resourcemanager_v1
from google.oauth2 import service_account

def grant_firestore_role():
    """Grant Firestore Editor and DataStore User roles to service account."""
    
    print("🔐 Updating Google Cloud IAM Roles...")
    
    try:
        credentials_path = Path(__file__).parent / 'serviceAccountKey.json'
        
        with open(credentials_path) as f:
            creds_json = json.load(f)
        
        project_id = creds_json.get('project_id')
        sa_email = creds_json.get('client_email')
        
        print(f"📝 Service Account: {sa_email}")
        print(f"📝 Project ID: {project_id}")
        
        # Use the same service account to authenticate to resource manager
        # This may fail if the service account doesn't have resourcemanager permissions
        credentials = service_account.Credentials.from_service_account_file(
            str(credentials_path),
            scopes=['https://www.googleapis.com/auth/cloud-platform']
        )
        
        # Create Resource Manager client
        client = resourcemanager_v1.ProjectsClient(credentials=credentials)
        
        project_name = f'projects/{project_id}'
        
        print(f"\n🌐 Fetching IAM policy for project...")
        
        # Get the IAM policy
        policy = client.get_iam_policy(resource=project_name)
        
        print(f"✅ Current bindings: {len(policy.bindings)}")
        
        # Define the roles we need
        roles_to_grant = [
            'roles/editor',  # Basic editor
            'roles/datastore.user',  # Datastore/Firestore user
            'roles/firebaseadmin.admin',  # Firebase admin
        ]
        
        sa_principal = f'serviceAccount:{sa_email}'
        
        print(f"\n📋 Roles to grant:")
        for role in roles_to_grant:
            print(f"   - {role}")
        
        # Update bindings
        for role in roles_to_grant:
            # Find or create binding for this role
            binding = None
            for b in policy.bindings:
                if b.role == role:
                    binding = b
                    break
            
            if binding is None:
                binding = resourcemanager_v1.Binding(role=role)
                policy.bindings.append(binding)
            
            # Add service account if not already present
            if sa_principal not in binding.members:
                binding.members.append(sa_principal)
                print(f"✅ Added {sa_email} to {role}")
            else:
                print(f"   Already has {role}")
        
        # Update the policy
        print(f"\n🔄 Updating IAM policy...")
        updated_policy = client.set_iam_policy(
            resource=project_name,
            policy=policy
        )
        
        print(f"✅ IAM policy updated successfully!")
        print(f"   New bindings: {len(updated_policy.bindings)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print(f"\n💡 Note: Service account may not have permission to modify IAM")
        print(f"   You may need to grant it manually in Google Cloud Console:")
        print(f"   1. Go to: https://console.cloud.google.com/iam-admin")
        print(f"   2. Find: {sa_email}")
        print(f"   3. Grant these roles:")
        print(f"      - Editor")
        print(f"      - Cloud Datastore User")
        print(f"      - Firebase Admin")
        return False

if __name__ == "__main__":
    grant_firestore_role()
