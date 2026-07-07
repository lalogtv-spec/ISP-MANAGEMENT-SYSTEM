#!/usr/bin/env python
"""Sync data to Firestore using REST API instead of Admin SDK."""

import os
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from api.models import Client, Application, Payment, Ticket
from google.oauth2 import service_account
from google.auth.transport.requests import Request
import requests

def get_access_token():
    """Get access token from service account."""
    credentials_path = Path(__file__).parent / 'serviceAccountKey.json'
    
    credentials = service_account.Credentials.from_service_account_file(
        str(credentials_path),
        scopes=['https://www.googleapis.com/auth/datastore']
    )
    
    auth_request = Request()
    credentials.refresh(auth_request)
    
    return credentials.token, credentials.service_account_email

def sync_via_rest_api():
    """Sync data using Firestore REST API."""
    
    try:
        access_token, sa_email = get_access_token()
        
        credentials_path = Path(__file__).parent / 'serviceAccountKey.json'
        with open(credentials_path) as f:
            creds_json = json.load(f)
        
        project_id = creds_json.get('project_id')
        
        print("🔥 SYNCING TO FIRESTORE VIA REST API")
        print("=" * 60)
        print(f"Service Account: {sa_email}")
        print(f"Project ID: {project_id}")
        print(f"Access Token: {access_token[:20]}...")
        
        base_url = f"https://firestore.googleapis.com/v1/projects/{project_id}/databases/(default)/documents"
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        # Test write
        print("\n📝 Testing write with REST API...")
        
        test_doc = {
            "fields": {
                "test": {"stringValue": "test"},
                "timestamp": {"timestampValue": "2026-06-22T10:00:00Z"}
            }
        }
        
        test_url = f"{base_url}/test_collection/test_doc"
        
        response = requests.patch(
            test_url,
            json=test_doc,
            headers=headers
        )
        
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.text[:200]}")
        
        if response.status_code == 200:
            print("✅ REST API write successful!")
            
            # Delete test doc
            requests.delete(test_url, headers=headers)
            
            # Now sync all data
            print("\n📋 Syncing all data...")
            
            # Sync clients
            clients = Client.objects.all()
            for i, client in enumerate(clients, 1):
                doc = {
                    "fields": {
                        "id": {"integerValue": str(client.id)},
                        "name": {"stringValue": client.name},
                        "email": {"stringValue": client.email or ""},
                        "phone": {"stringValue": client.phone or ""},
                        "address": {"stringValue": client.address or ""},
                        "plan": {"stringValue": client.plan or ""},
                        "fee": {"doubleValue": str(client.monthly_fee or 0)},
                        "status": {"stringValue": client.status or "active"},
                    }
                }
                
                url = f"{base_url}/clients/{client.id}"
                r = requests.patch(url, json=doc, headers=headers)
                status = "✅" if r.status_code == 200 else "❌"
                print(f"   {status} Client {i}/{len(clients)}: {client.name}")
            
            return True
        else:
            print(f"❌ REST API failed: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    sync_via_rest_api()
