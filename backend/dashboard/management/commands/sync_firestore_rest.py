"""
Django management command to sync database to Firestore using REST API.
Usage: python manage.py sync_to_firestore_rest --all
"""

import json
from pathlib import Path
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError
from google.oauth2 import service_account
from google.auth.transport.requests import Request
import requests

from api.models import Client, Application, Payment, Ticket


class Command(BaseCommand):
    help = 'Sync database records to Firestore using REST API'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clients',
            action='store_true',
            help='Sync only clients'
        )
        parser.add_argument(
            '--applications',
            action='store_true',
            help='Sync only applications'
        )
        parser.add_argument(
            '--payments',
            action='store_true',
            help='Sync only payments'
        )
        parser.add_argument(
            '--tickets',
            action='store_true',
            help='Sync only tickets'
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Sync all records'
        )

    def get_access_token(self):
        """Get access token from service account."""
        try:
            # Get backend directory (4 levels up from this file)
            credentials_path = Path(__file__).parent.parent.parent.parent / 'serviceAccountKey.json'
            
            credentials = service_account.Credentials.from_service_account_file(
                str(credentials_path),
                scopes=['https://www.googleapis.com/auth/datastore']
            )
            
            auth_request = Request()
            credentials.refresh(auth_request)
            
            return credentials.token
        except Exception as e:
            raise CommandError(f'Failed to get access token: {e}')

    def get_project_id(self):
        """Get project ID from service account."""
        try:
            # Get backend directory (4 levels up from this file)
            credentials_path = Path(__file__).parent.parent.parent.parent / 'serviceAccountKey.json'
            
            with open(credentials_path) as f:
                creds_json = json.load(f)
            
            return creds_json.get('project_id')
        except Exception as e:
            raise CommandError(f'Failed to get project ID: {e}')

    def convert_to_firestore_value(self, value):
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

    def sync_clients(self, headers, base_url):
        """Sync all clients."""
        self.stdout.write('\n📋 Syncing Clients...')
        clients = Client.objects.all()
        
        success_count = 0
        for client in clients:
            try:
                doc = {
                    "fields": {
                        "client_id": self.convert_to_firestore_value(client.client_id),
                        "name": self.convert_to_firestore_value(client.name),
                        "email": self.convert_to_firestore_value(client.email),
                        "phone": self.convert_to_firestore_value(client.phone),
                        "address": self.convert_to_firestore_value(client.address),
                        "plan": self.convert_to_firestore_value(client.plan),
                        "fee": self.convert_to_firestore_value(float(client.fee)),
                        "status": self.convert_to_firestore_value(client.status),
                        "balance": self.convert_to_firestore_value(float(client.balance)),
                        "due_date": self.convert_to_firestore_value(client.due_date),
                        "joined": self.convert_to_firestore_value(client.joined),
                    }
                }
                
                url = f"{base_url}/clients/{client.client_id}"
                r = requests.patch(url, json=doc, headers=headers)
                
                if r.status_code == 200:
                    success_count += 1
                    self.stdout.write(self.style.SUCCESS(f'   ✅ {client.client_id}: {client.name}'))
                else:
                    self.stdout.write(self.style.ERROR(f'   ❌ {client.client_id}: {r.status_code}'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'   ❌ {client.client_id}: {e}'))
        
        self.stdout.write(f'   ✅ Synced {success_count}/{len(clients)} clients\n')
        return success_count

    def sync_applications(self, headers, base_url):
        """Sync all applications."""
        self.stdout.write('📋 Syncing Applications...')
        apps = Application.objects.all()
        
        success_count = 0
        for app in apps:
            try:
                doc = {
                    "fields": {
                        "app_id": self.convert_to_firestore_value(app.app_id),
                        "name": self.convert_to_firestore_value(app.name),
                        "email": self.convert_to_firestore_value(app.email),
                        "phone": self.convert_to_firestore_value(app.phone),
                        "address": self.convert_to_firestore_value(app.address),
                        "plan": self.convert_to_firestore_value(app.plan),
                        "status": self.convert_to_firestore_value(app.status),
                        "date": self.convert_to_firestore_value(app.date),
                    }
                }
                
                url = f"{base_url}/applications/{app.app_id}"
                r = requests.patch(url, json=doc, headers=headers)
                
                if r.status_code == 200:
                    success_count += 1
                    self.stdout.write(self.style.SUCCESS(f'   ✅ {app.app_id}: {app.name}'))
                else:
                    self.stdout.write(self.style.ERROR(f'   ❌ {app.app_id}: {r.status_code}'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'   ❌ {app.app_id}: {e}'))
        
        self.stdout.write(f'   ✅ Synced {success_count}/{len(apps)} applications\n')
        return success_count

    def sync_payments(self, headers, base_url):
        """Sync all payments."""
        self.stdout.write('📋 Syncing Payments...')
        payments = Payment.objects.all()
        
        success_count = 0
        for payment in payments:
            try:
                doc = {
                    "fields": {
                        "payment_id": self.convert_to_firestore_value(payment.payment_id),
                        "client": self.convert_to_firestore_value(payment.client),
                        "amount": self.convert_to_firestore_value(float(payment.amount)),
                        "period": self.convert_to_firestore_value(payment.period),
                        "method": self.convert_to_firestore_value(payment.method),
                        "status": self.convert_to_firestore_value(payment.status),
                        "date": self.convert_to_firestore_value(payment.date),
                    }
                }
                
                url = f"{base_url}/payments/{payment.payment_id}"
                r = requests.patch(url, json=doc, headers=headers)
                
                if r.status_code == 200:
                    success_count += 1
                    self.stdout.write(self.style.SUCCESS(f'   ✅ {payment.payment_id}: {payment.client}'))
                else:
                    self.stdout.write(self.style.ERROR(f'   ❌ {payment.payment_id}: {r.status_code}'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'   ❌ {payment.payment_id}: {e}'))
        
        self.stdout.write(f'   ✅ Synced {success_count}/{len(payments)} payments\n')
        return success_count

    def sync_tickets(self, headers, base_url):
        """Sync all tickets."""
        self.stdout.write('📋 Syncing Tickets...')
        tickets = Ticket.objects.all()
        
        success_count = 0
        for ticket in tickets:
            try:
                doc = {
                    "fields": {
                        "ticket_id": self.convert_to_firestore_value(ticket.ticket_id),
                        "client": self.convert_to_firestore_value(ticket.client),
                        "category": self.convert_to_firestore_value(ticket.category),
                        "priority": self.convert_to_firestore_value(ticket.priority),
                        "status": self.convert_to_firestore_value(ticket.status),
                        "description": self.convert_to_firestore_value(ticket.description),
                        "assigned": self.convert_to_firestore_value(ticket.assigned),
                        "created": self.convert_to_firestore_value(ticket.created),
                    }
                }
                
                url = f"{base_url}/tickets/{ticket.ticket_id}"
                r = requests.patch(url, json=doc, headers=headers)
                
                if r.status_code == 200:
                    success_count += 1
                    self.stdout.write(self.style.SUCCESS(f'   ✅ {ticket.ticket_id}: {ticket.client}'))
                else:
                    self.stdout.write(self.style.ERROR(f'   ❌ {ticket.ticket_id}: {r.status_code}'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'   ❌ {ticket.ticket_id}: {e}'))
        
        self.stdout.write(f'   ✅ Synced {success_count}/{len(tickets)} tickets\n')
        return success_count

    def handle(self, *args, **options):
        """Main command handler."""
        
        self.stdout.write(self.style.SUCCESS('\n🔥 FIRESTORE SYNC VIA REST API'))
        self.stdout.write('=' * 60)
        
        try:
            access_token = self.get_access_token()
            project_id = self.get_project_id()
            
            base_url = f"https://firestore.googleapis.com/v1/projects/{project_id}/databases/(default)/documents"
            
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            total = 0
            
            # Determine what to sync
            sync_all = options['all']
            
            if sync_all or options['clients']:
                total += self.sync_clients(headers, base_url)
            
            if sync_all or options['applications']:
                total += self.sync_applications(headers, base_url)
            
            if sync_all or options['payments']:
                total += self.sync_payments(headers, base_url)
            
            if sync_all or options['tickets']:
                total += self.sync_tickets(headers, base_url)
            
            self.stdout.write('=' * 60)
            self.stdout.write(self.style.SUCCESS(f'✅ Total records synced: {total}'))
            self.stdout.write('=' * 60)
            
        except Exception as e:
            raise CommandError(f'Sync failed: {e}')
