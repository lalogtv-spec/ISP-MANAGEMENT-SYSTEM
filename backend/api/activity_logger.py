"""
Utility functions for logging system activities
"""
from .models import ActivityLog
from decimal import Decimal


def log_client_created(client_id, client_name, performed_by='System'):
    """Log when a new client is created"""
    ActivityLog.objects.create(
        activity_type='client_created',
        entity_type='Client',
        entity_id=client_id,
        entity_name=client_name,
        description=f'New client {client_name} was created',
        performed_by=performed_by,
    )


def log_client_edited(client_id, client_name, changes_dict, performed_by='System'):
    """
    Log when a client is edited
    changes_dict should be {'field_name': {'old': old_value, 'new': new_value}, ...}
    """
    changes_text = ', '.join([
        f"{k.replace('_', ' ').title()} changed from '{v['old']}' to '{v['new']}'"
        for k, v in changes_dict.items()
    ])
    
    ActivityLog.objects.create(
        activity_type='client_edited',
        entity_type='Client',
        entity_id=client_id,
        entity_name=client_name,
        description=f'Client {client_name} was edited: {changes_text}',
        old_value=str(changes_dict),
        performed_by=performed_by,
    )


def log_client_deleted(client_id, client_name, performed_by='System'):
    """Log when a client is deleted"""
    ActivityLog.objects.create(
        activity_type='client_deleted',
        entity_type='Client',
        entity_id=client_id,
        entity_name=client_name,
        description=f'Client {client_name} was permanently deleted',
        performed_by=performed_by,
    )


def log_payment_recorded(payment_id, client_name, amount, method, performed_by='System'):
    """Log when a payment is recorded"""
    ActivityLog.objects.create(
        activity_type='payment_recorded',
        entity_type='Payment',
        entity_id=payment_id,
        entity_name=client_name,
        description=f'Payment of ₱{amount} received from {client_name} via {method}',
        amount=Decimal(str(amount)),
        performed_by=performed_by,
    )


def log_application_approved(app_id, applicant_name, plan, performed_by='System'):
    """Log when an application is approved"""
    ActivityLog.objects.create(
        activity_type='application_approved',
        entity_type='Application',
        entity_id=app_id,
        entity_name=f"{applicant_name} - {plan}",
        description=f'Application {app_id} for {applicant_name} ({plan}) was APPROVED',
        performed_by=performed_by,
    )


def log_application_declined(app_id, applicant_name, plan, reason='', performed_by='System'):
    """Log when an application is declined"""
    reason_text = f' - Reason: {reason}' if reason else ''
    ActivityLog.objects.create(
        activity_type='application_declined',
        entity_type='Application',
        entity_id=app_id,
        entity_name=f"{applicant_name} - {plan}",
        description=f'Application {app_id} for {applicant_name} ({plan}) was DECLINED{reason_text}',
        performed_by=performed_by,
    )


def log_application_deleted(app_id, applicant_name, plan, performed_by='System'):
    """Log when an application is deleted"""
    ActivityLog.objects.create(
        activity_type='application_deleted',
        entity_type='Application',
        entity_id=app_id,
        entity_name=f"{applicant_name} - {plan}",
        description=f'Application {app_id} for {applicant_name} ({plan}) was deleted',
        performed_by=performed_by,
    )
