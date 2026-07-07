"""
Django management command to sync database records to Firebase.

Usage:
    python manage.py sync_to_firebase --all
    python manage.py sync_to_firebase --colab
    python manage.py sync_to_firebase --facial-biometrics
"""

from __future__ import annotations

import base64
from pathlib import Path

from django.core.management.base import BaseCommand

from firebase_service import firebase
from api.models import Client, Application, Payment, Ticket
from security.models import BiometricData, UserSecurityProfile


class Command(BaseCommand):
    help = 'Sync database records to Firebase Firestore'

    def add_arguments(self, parser):
        parser.add_argument('--clients', action='store_true', help='Sync clients to Firebase')
        parser.add_argument('--applications', action='store_true', help='Sync applications to Firebase')
        parser.add_argument('--payments', action='store_true', help='Sync payments to Firebase')
        parser.add_argument('--tickets', action='store_true', help='Sync tickets to Firebase')
        parser.add_argument('--facial-biometrics', action='store_true', help='Sync facial biometrics to Firebase')
        parser.add_argument('--colab', action='store_true', help='Sync datasets needed for Colab analysis')
        parser.add_argument('--all', action='store_true', help='Sync all records to Firebase')

    def handle(self, *args, **options):
        if not firebase.is_connected():
            self.stdout.write(self.style.ERROR('Firebase is not connected!'))
            return

        self.stdout.write(self.style.SUCCESS('\n' + '=' * 60))
        self.stdout.write(self.style.SUCCESS('SYNCING DATABASE TO FIREBASE'))
        self.stdout.write(self.style.SUCCESS('=' * 60 + '\n'))

        sync_all = options['all']
        sync_colab = options['colab']
        sync_clients = options['clients'] or sync_all or sync_colab
        sync_apps = options['applications'] or sync_all or sync_colab
        sync_payments = options['payments'] or sync_all or sync_colab
        sync_tickets = options['tickets'] or sync_all
        sync_faces = options['facial_biometrics'] or sync_all or sync_colab

        if not any([sync_clients, sync_apps, sync_payments, sync_tickets, sync_faces]):
            self.stdout.write(self.style.WARNING('No sync options selected. Use --all, --colab, or specify collections.'))
            return

        if sync_clients:
            self._sync_clients()
        if sync_apps:
            self._sync_applications()
        if sync_payments:
            self._sync_payments()
        if sync_tickets:
            self._sync_tickets()
        if sync_faces:
            self._sync_facial_biometrics()

        self.stdout.write(self.style.SUCCESS('\n' + '=' * 60))
        self.stdout.write(self.style.SUCCESS('Sync completed!'))
        self.stdout.write(self.style.SUCCESS('=' * 60 + '\n'))

    def _sync_clients(self):
        self.stdout.write(self.style.WARNING('Syncing Clients...'))
        clients = Client.objects.all()
        if not clients.exists():
            self.stdout.write(self.style.WARNING('   No clients found'))
            return

        count = 0
        for client in clients:
            try:
                firebase.save_to_firestore(
                    collection='clients',
                    doc_id=str(client.client_id),
                    data={
                        'id': str(client.client_id),
                        'name': client.name,
                        'email': client.email,
                        'phone': client.phone,
                        'address': client.address,
                        'plan': client.plan,
                        'fee': float(client.fee),
                        'status': client.status,
                        'balance': float(client.balance),
                        'due_date': client.due_date.isoformat() if client.due_date else None,
                        'joined': client.joined.isoformat() if client.joined else None,
                        'created_at': client.created_at.isoformat(),
                        'updated_at': client.updated_at.isoformat(),
                    }
                )
                count += 1
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'   Error syncing {client.client_id}: {e}'))
        self.stdout.write(self.style.SUCCESS(f'   Synced {count}/{len(clients)} clients\n'))

    def _sync_applications(self):
        self.stdout.write(self.style.WARNING('Syncing Applications...'))
        apps = Application.objects.all()
        if not apps.exists():
            self.stdout.write(self.style.WARNING('   No applications found'))
            return

        count = 0
        for app in apps:
            try:
                firebase.save_to_firestore(
                    collection='applications',
                    doc_id=str(app.app_id),
                    data={
                        'id': str(app.app_id),
                        'name': app.name,
                        'email': app.email,
                        'phone': app.phone,
                        'address': app.address,
                        'plan': app.plan,
                        'status': app.status,
                        'date': app.date.isoformat() if app.date else None,
                        'user_id': str(app.user.id) if app.user else None,
                        'user_email': app.user.email if app.user else None,
                        'created_at': app.created_at.isoformat(),
                        'updated_at': app.updated_at.isoformat(),
                    }
                )
                count += 1
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'   Error syncing {app.app_id}: {e}'))
        self.stdout.write(self.style.SUCCESS(f'   Synced {count}/{len(apps)} applications\n'))

    def _sync_payments(self):
        self.stdout.write(self.style.WARNING('Syncing Payments...'))
        payments = Payment.objects.all()
        if not payments.exists():
            self.stdout.write(self.style.WARNING('   No payments found'))
            return

        count = 0
        for payment in payments:
            try:
                firebase.save_to_firestore(
                    collection='payments',
                    doc_id=str(payment.payment_id),
                    data={
                        'id': str(payment.payment_id),
                        'client': payment.client,
                        'amount': float(payment.amount),
                        'period': payment.period,
                        'method': payment.method,
                        'status': payment.status,
                        'date': payment.date.isoformat() if payment.date else None,
                        'created_at': payment.created_at.isoformat(),
                        'updated_at': payment.updated_at.isoformat(),
                    }
                )
                count += 1
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'   Error syncing {payment.payment_id}: {e}'))
        self.stdout.write(self.style.SUCCESS(f'   Synced {count}/{len(payments)} payments\n'))

    def _sync_tickets(self):
        self.stdout.write(self.style.WARNING('Syncing Tickets...'))
        tickets = Ticket.objects.all()
        if not tickets.exists():
            self.stdout.write(self.style.WARNING('   No tickets found'))
            return

        count = 0
        for ticket in tickets:
            try:
                firebase.save_to_firestore(
                    collection='tickets',
                    doc_id=str(ticket.ticket_id),
                    data={
                        'id': str(ticket.ticket_id),
                        'client': ticket.client,
                        'category': ticket.category,
                        'priority': ticket.priority,
                        'status': ticket.status,
                        'description': ticket.description,
                        'assigned': ticket.assigned,
                        'created': ticket.created.isoformat() if ticket.created else None,
                        'created_at': ticket.created_at.isoformat(),
                        'updated_at': ticket.updated_at.isoformat(),
                    }
                )
                count += 1
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'   Error syncing {ticket.ticket_id}: {e}'))
        self.stdout.write(self.style.SUCCESS(f'   Synced {count}/{len(tickets)} tickets\n'))

    def _sync_facial_biometrics(self):
        self.stdout.write(self.style.WARNING('Syncing Facial Biometrics...'))
        biometrics = BiometricData.objects.filter(biometric_type='facial', is_active=True).select_related('user')
        if not biometrics.exists():
            self.stdout.write(self.style.WARNING('   No facial biometrics found'))
            return

        count = 0
        for biometric in biometrics:
            try:
                try:
                    profile = UserSecurityProfile.objects.get(user=biometric.user)
                except UserSecurityProfile.DoesNotExist:
                    profile = None

                sample_b64 = ''
                sample_name = ''
                if biometric.sample_image_path:
                    sample_path = Path(biometric.sample_image_path)
                    if sample_path.exists():
                        sample_b64 = base64.b64encode(sample_path.read_bytes()).decode('ascii')
                        sample_name = sample_path.name

                firebase.save_to_firestore(
                    collection='facial_biometrics',
                    doc_id=str(biometric.id),
                    data={
                        'id': str(biometric.id),
                        'user_id': biometric.user_id,
                        'username': biometric.user.username,
                        'email': biometric.user.email,
                        'facial_data_enrolled': bool(profile and profile.facial_data_enrolled),
                        'quality_score': float(biometric.enrollment_quality_score),
                        'confidence': float(biometric.enrollment_confidence),
                        'enrolled_at': biometric.enrolled_at.isoformat() if biometric.enrolled_at else None,
                        'sample_image_path': biometric.sample_image_path,
                        'sample_image_name': sample_name,
                        'sample_image_b64': sample_b64,
                        'template_data': biometric.template_data,
                        'template_hash': biometric.template_hash,
                        'is_active': biometric.is_active,
                        'created_at': biometric.created_at.isoformat(),
                        'updated_at': biometric.updated_at.isoformat(),
                    }
                )
                count += 1
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'   Error syncing facial biometric {biometric.id}: {e}'))

        self.stdout.write(self.style.SUCCESS(f'   Synced {count}/{len(biometrics)} facial biometrics\n'))
