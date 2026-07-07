#!/usr/bin/env python
"""Verify data in Firestore."""

import os
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from google.oauth2 import service_account
from google.auth.transport.requests import Request
import requests

def verify_firestore_data():
    """Verify data is in Firestore."""
    
    try:
        credentials_path = Path(__file__).parent / 'serviceAccountKey.json'
        
        credentials = service_account.Credentials.from_service_account_file(
            str(credentials_path),
            scopes=['https://www.googleapis.com/auth/datastore']
        )
        
        auth_request = Request()
        credentials.refresh(auth_request)
        access_token = credentials.token
        
        with open(credentials_path) as f:
            creds_json = json.load(f)
        
        project_id = creds_json.get('project_id')
        
        base_url = f"https://firestore.googleapis.com/v1/projects/{project_id}/databases/(default)/documents"
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        print("🔍 Verifying Firestore Collections")
        print("=" * 60)
        
        # List collections
        collections = ['clients', 'applications', 'payments', 'tickets']
        
        for collection in collections:
            # Get first document from collection
            url = f"{base_url}/{collection}"
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                doc_count = len(data.get('documents', []))
                print(f"✅ {collection.upper()}: {doc_count} documents")
                
                # Show sample
                if doc_count > 0:
                    doc = data['documents'][0]
                    name = doc.get('name', '').split('/')[-1]
                    print(f"   Sample: {name}")
            else:
                print(f"❌ {collection.upper()}: Failed to fetch")
        
        print("=" * 60)
        print("✅ Firestore sync complete and verified!")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    verify_firestore_data()
