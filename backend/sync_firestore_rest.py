#!/usr/bin/env python
"""Sync all data to Firestore using REST API."""

import os
import sys
import json
from pathlib import Path
from datetime import datetime

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
    
    return credentials.token

def convert_to_firestore_value(value):
    """Convert Python value to Firestore value format."""
    if value is None:
        return {"nullValue": None}
    elif isinstance(value, bool):
        return {"booleanValue": value}
    elif isinstance(value, int):
        return {"integerValue": str(value)}
    elif isinstance(value, float):
        return {"doubleValue": str(value)}
    elif isinstance(value, str):
        return {"stringValue": value}
    elif isinstance(value, datetime):
        return {"timestampValue": value.isoformat() + "Z"}
    else:
        return {"stringValue": str(value)}

def sync_clients(headers, base_url):
    """Sync all clients."""
    print("\n📋 Syncing Clients...")
    clients = Client.objects.all()
    
    success_count = 0
    for client in clients:
        try:
            doc = {
                "fields": {
                    "client_id": convert_to_firestore_value(client.client_id),
                    "name": convert_to_firestore_value(client.name),
                    "email": convert_to_firestore_value(client.email),
                    "phone": convert_to_firestore_value(client.phone),
                    "address": convert_to_firestore_value(client.address),
                    "plan": convert_to_firestore_value(client.plan),
                    "fee": convert_to_firestore_value(float(client.fee)),
                    "status": convert_to_firestore_value(client.status),
                    "balance": convert_to_firestore_value(float(client.balance)),
                    "due_date": convert_to_firestore_value(client.due_date),
                    "joined": convert_to_firestore_value(client.joined),
                }
            }
            
            url = f"{base_url}/clients/{client.client_id}"
            r = requests.patch(url, json=doc, headers=headers)
            
            if r.status_code == 200:
                success_count += 1
                print(f"   ✅ {client.client_id}: {client.name}")
            else:
                print(f"   ❌ {client.client_id}: {r.status_code}")
        except Exception as e:
            print(f"   ❌ {client.client_id}: {e}")
    
    print(f"   ✅ Synced {success_count}/{len(clients)} clients")
    return success_count

def sync_applications(headers, base_url):
    """Sync all applications."""
    print("\n📋 Syncing Applications...")
    apps = Application.objects.all()
    
    success_count = 0
    for app in apps:
        try:
            doc = {
                "fields": {
                    "app_id": convert_to_firestore_value(app.app_id),
                    "name": convert_to_firestore_value(app.name),
                    "email": convert_to_firestore_value(app.email),
                    "phone": convert_to_firestore_value(app.phone),
                    "address": convert_to_firestore_value(app.address),
                    "plan": convert_to_firestore_value(app.plan),
                    "status": convert_to_firestore_value(app.status),
                    "date": convert_to_firestore_value(app.date),
                }
            }
            
            url = f"{base_url}/applications/{app.app_id}"
            r = requests.patch(url, json=doc, headers=headers)
            
            if r.status_code == 200:
                success_count += 1
                print(f"   ✅ {app.app_id}: {app.name}")
            else:
                print(f"   ❌ {app.app_id}: {r.status_code}")
        except Exception as e:
            print(f"   ❌ {app.app_id}: {e}")
    
    print(f"   ✅ Synced {success_count}/{len(apps)} applications")
    return success_count

def sync_payments(headers, base_url):
    """Sync all payments."""
    print("\n📋 Syncing Payments...")
    payments = Payment.objects.all()
    
    success_count = 0
    for payment in payments:
        try:
            doc = {
                "fields": {
                    "payment_id": convert_to_firestore_value(payment.payment_id),
                    "client": convert_to_firestore_value(payment.client),
                    "amount": convert_to_firestore_value(float(payment.amount)),
                    "period": convert_to_firestore_value(payment.period),
                    "method": convert_to_firestore_value(payment.method),
                    "status": convert_to_firestore_value(payment.status),
                    "date": convert_to_firestore_value(payment.date),
                }
            }
            
            url = f"{base_url}/payments/{payment.payment_id}"
            r = requests.patch(url, json=doc, headers=headers)
            
            if r.status_code == 200:
                success_count += 1
                print(f"   ✅ {payment.payment_id}: {payment.client}")
            else:
                print(f"   ❌ {payment.payment_id}: {r.status_code}")
        except Exception as e:
            print(f"   ❌ {payment.payment_id}: {e}")
    
    print(f"   ✅ Synced {success_count}/{len(payments)} payments")
    return success_count

def sync_tickets(headers, base_url):
    """Sync all tickets."""
    print("\n📋 Syncing Tickets...")
    tickets = Ticket.objects.all()
    
    success_count = 0
    for ticket in tickets:
        try:
            doc = {
                "fields": {
                    "ticket_id": convert_to_firestore_value(ticket.ticket_id),
                    "client": convert_to_firestore_value(ticket.client),
                    "category": convert_to_firestore_value(ticket.category),
                    "priority": convert_to_firestore_value(ticket.priority),
                    "status": convert_to_firestore_value(ticket.status),
                    "description": convert_to_firestore_value(ticket.description),
                    "assigned": convert_to_firestore_value(ticket.assigned),
                    "created": convert_to_firestore_value(ticket.created),
                }
            }
            
            url = f"{base_url}/tickets/{ticket.ticket_id}"
            r = requests.patch(url, json=doc, headers=headers)
            
            if r.status_code == 200:
                success_count += 1
                print(f"   ✅ {ticket.ticket_id}: {ticket.client}")
            else:
                print(f"   ❌ {ticket.ticket_id}: {r.status_code}")
        except Exception as e:
            print(f"   ❌ {ticket.ticket_id}: {e}")
    
    print(f"   ✅ Synced {success_count}/{len(tickets)} tickets")
    return success_count

def main():
    """Main sync function."""
    try:
        print("🔥 FIRESTORE SYNC VIA REST API")
        print("=" * 60)
        
        access_token = get_access_token()
        
        credentials_path = Path(__file__).parent / 'serviceAccountKey.json'
        with open(credentials_path) as f:
            creds_json = json.load(f)
        
        project_id = creds_json.get('project_id')
        
        base_url = f"https://firestore.googleapis.com/v1/projects/{project_id}/databases/(default)/documents"
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        # Sync all data
        total = 0
        total += sync_clients(headers, base_url)
        total += sync_applications(headers, base_url)
        total += sync_payments(headers, base_url)
        total += sync_tickets(headers, base_url)
        
        print("\n" + "=" * 60)
        print(f"✅ Total records synced: {total}")
        print("=" * 60)
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
