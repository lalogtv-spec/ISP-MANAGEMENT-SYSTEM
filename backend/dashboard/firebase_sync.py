"""
Firebase sync utilities for ISP Management System
Usage in views:
    from dashboard.firebase_sync import sync_client, sync_application, sync_payment, sync_ticket
    
    # When creating a client:
    client = Client.objects.create(...)
    sync_client(client)
"""

import base64
from pathlib import Path

from firebase_service import firebase
from security.models import BiometricData, UserSecurityProfile


def sync_client(client):
    """Sync a client to Firebase"""
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
                'due_date': client.due_date.isoformat(),
                'joined': client.joined.isoformat() if client.joined else None,
                'created_at': client.created_at.isoformat(),
                'updated_at': client.updated_at.isoformat()
            }
        )
        return True
    except Exception as e:
        print(f"Error syncing client {client.client_id}: {e}")
        return False


def sync_application(application):
    """Sync an application to Firebase"""
    try:
        firebase.save_to_firestore(
            collection='applications',
            doc_id=str(application.app_id),
            data={
                'id': str(application.app_id),
                'name': application.name,
                'email': application.email,
                'phone': application.phone,
                'address': application.address,
                'plan': application.plan,
                'status': application.status,
                'date': application.date.isoformat(),
                'user_id': str(application.user.id) if application.user else None,
                'user_email': application.user.email if application.user else None,
                'created_at': application.created_at.isoformat(),
                'updated_at': application.updated_at.isoformat()
            }
        )
        return True
    except Exception as e:
        print(f"Error syncing application {application.app_id}: {e}")
        return False


def sync_payment(payment):
    """Sync a payment to Firebase"""
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
                'date': payment.date.isoformat(),
                'created_at': payment.created_at.isoformat(),
                'updated_at': payment.updated_at.isoformat()
            }
        )
        return True
    except Exception as e:
        print(f"Error syncing payment {payment.payment_id}: {e}")
        return False


def sync_ticket(ticket):
    """Sync a ticket to Firebase"""
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
                'created': ticket.created.isoformat(),
                'created_at': ticket.created_at.isoformat(),
                'updated_at': ticket.updated_at.isoformat()
            }
        )
        return True
    except Exception as e:
        print(f"Error syncing ticket {ticket.ticket_id}: {e}")
        return False


def sync_facial_biometric(biometric):
    """Sync a facial biometric record to Firebase."""
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
        return True
    except Exception as e:
        print(f"Error syncing facial biometric {biometric.id}: {e}")
        return False
