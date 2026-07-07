"""
Admin views for notification management and monitoring
"""
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import HttpResponseForbidden, JsonResponse
from django.db.models import Q, Count, Sum
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from api.models import Client, NotificationTemplate, Payment, ActivityLog, Ticket, OverdueNotification
from api.notification_service import NotificationService
from dashboard.forms import NotificationTemplateForm
from security.models import AuditLog as SecurityAuditLog


def is_admin(user):
    """Check if user is admin"""
    return user.is_staff or user.is_superuser


def is_admin_view(view_func):
    """Decorator to ensure only admins can access"""
    @login_required
    def wrapper(request, *args, **kwargs):
        if not is_admin(request.user):
            return HttpResponseForbidden("Access denied. Admin only.")
        return view_func(request, *args, **kwargs)
    return wrapper


def ensure_default_notification_templates():
    """Create missing default notification templates so the admin UI shows new types."""
    default_templates = NotificationService.DEFAULT_TEMPLATES
    for template_type, values in default_templates.items():
        for channel in ['Email', 'SMS']:
            if not NotificationTemplate.objects.filter(template_type=template_type, channel=channel).exists():
                template_id = f"{template_type.replace(' ', '_')}_{channel}"
                subject = values.get('subject', '') if channel == 'Email' else ''
                body = values.get('email_body' if channel == 'Email' else 'sms_body', '')
                NotificationTemplate.objects.create(
                    template_id=template_id,
                    template_type=template_type,
                    channel=channel,
                    subject=subject,
                    body=body,
                )


def get_admin_notification_count():
    """Calculate admin sidebar badge count consistently across admin views."""
    unread_tickets = Ticket.objects.exclude(status='Resolved').filter(notification_read=False, hide_from_notifications=False).count()
    unread_payments = Payment.objects.filter(notification_read=False, hide_from_notifications=False).count()
    unread_ticket_activities = ActivityLog.objects.filter(
        entity_type='Ticket',
        activity_type='ticket_reschedule_requested',
        is_new=True,
    ).count()
    return unread_tickets + unread_payments + unread_ticket_activities


@is_admin_view
def sms_notification_log(request):
    # SMS log view removed. Redirect to notification dashboard.
    return render(request, 'admin/notification_dashboard.html', {
        'message': 'SMS logs removed',
        'notification_count': get_admin_notification_count(),
    })


@is_admin_view
def email_notification_log(request):
    # Email log view removed. Redirect to notification dashboard.
    return render(request, 'admin/notification_dashboard.html', {
        'message': 'Email logs removed',
        'notification_count': get_admin_notification_count(),
    })


@is_admin_view
def notification_dashboard(request):
    """
    Main notification dashboard with statistics and recent activity.
    """
    search_query = request.GET.get('q', '').strip()
    category_filter = request.GET.get('category', '').strip()

    # Overall statistics
    # Overall statistics (from OverdueNotification)
    total_notifications = OverdueNotification.objects.count()

    today = timezone.now().date()
    sent_today = OverdueNotification.objects.filter(sent_at__date=today).count()

    # Last 7 days statistics
    start_date = today - timedelta(days=7)
    last_7_days = OverdueNotification.objects.filter(sent_at__date__gte=start_date).count()

    # Notification type breakdown
    overdue_count = OverdueNotification.objects.filter(notification_type__in=['First Notice', 'Second Notice']).count()
    final_warning_count = OverdueNotification.objects.filter(notification_type='Second Notice').count()
    disconnection_count = OverdueNotification.objects.filter(notification_type='Disconnection Warning').count()

    # Recent notifications
    recent_notifications = OverdueNotification.objects.order_by('-sent_at')[:5]
    
    # Recent Activities (System changes)
    recent_activities = ActivityLog.objects.order_by('-created_at')[:10]
    
    # Client and ticket statistics
    total_clients = Client.objects.count()
    active_clients = Client.objects.filter(status='Active').count()
    overdue_clients = Client.objects.filter(status='Overdue').count()
    disconnected_clients = Client.objects.filter(status='Disconnected').count()
    tickets_open = Ticket.objects.filter(status__in=['Pending', 'In Progress']).count()
    
    # Revenue calculations - only count verified payments
    total_revenue = Payment.objects.filter(status='Verified').aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')
    
    # Monthly revenue - current month only
    current_month_start = today.replace(day=1)
    if today.month == 12:
        next_month = today.replace(year=today.year + 1, month=1)
    else:
        next_month = today.replace(month=today.month + 1)
    
    monthly_revenue = Payment.objects.filter(
        status='Verified',
        date__gte=current_month_start,
        date__lt=next_month
    ).aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')
    
    # Count unread notifications for the dashboard badge (tickets + payments)
    unread_tickets = Ticket.objects.filter(notification_read=False, hide_from_notifications=False).count()
    unread_payments = Payment.objects.filter(notification_read=False, hide_from_notifications=False).count()
    notification_count = unread_tickets + unread_payments

    # Combine SMS and Email notifications into a single list
    active_notifications = []

    def notification_category(notification_type):
        if notification_type == 'Overdue Notice':
            return 'Payment Overdue Alert'
        if notification_type == 'Final Warning':
            return 'Warning'
        if notification_type == 'Disconnection Notice':
            return 'Disconnection'
        if notification_type == 'Payment Reminder':
            return 'Payment Reminder'
        if notification_type == 'Payment Receipt':
            return 'Payment Receipt'
        return 'General Notification'

    # Add OverdueNotification entries
    for n in OverdueNotification.objects.filter(hide_from_notifications=False).order_by('-sent_at'):
        active_notifications.append({
            'id': n.notification_id,
            'type': 'overdue',
            'category': notification_category(n.notification_type),
            'title': n.notification_type,
            'client_name': n.client,
            'channel': 'Overdue',
            'description': n.email_response or n.sms_response or f"Billing notice: {n.notification_type}",
            'amount_due': n.amount_due,
            'ticket_id': None,
            'sent_at': n.sent_at or n.created_at,
            'is_new': False,
            'status': n.status,
        })

    # Add active support tickets (including scheduled and in-progress tickets)
    for ticket in Ticket.objects.exclude(status='Resolved').filter(hide_from_notifications=False).order_by('-created_at'):
        notification_status = 'Read' if ticket.notification_read else 'New'
        active_notifications.append({
            'id': ticket.ticket_id,
            'type': 'ticket',
            'category': 'Support Tickets',
            'title': f"{ticket.category} ({ticket.priority})",
            'client_name': ticket.client,
            'channel': 'Ticket',
            'description': f"{ticket.description} [{ticket.status}]",
            'amount_due': None,
            'ticket_id': ticket.ticket_id,
            'sent_at': ticket.created_at,
            'is_new': True,
            'status': notification_status,
        })

    # Add ticket reschedule request activities so admin can see pending client reschedule requests
    for activity in ActivityLog.objects.filter(
        entity_type='Ticket',
        activity_type='ticket_reschedule_requested'
    ).order_by('-created_at'):
        active_notifications.append({
            'id': f'activity-{activity.activity_id}',
            'type': 'ticket_activity',
            'category': 'Support Tickets',
            'title': 'Reschedule Request',
            'client_name': activity.entity_name,
            'channel': 'Ticket',
            'description': activity.description,
            'amount_due': None,
            'ticket_id': activity.entity_id,
            'sent_at': activity.created_at,
            'is_new': activity.is_new,
            'status': 'Read' if not activity.is_new else 'New',
        })

    # Add recent verified payments (Payment Received)
    for payment in Payment.objects.filter(status='Verified', hide_from_notifications=False).order_by('-date')[:20]:
        payment_status = 'Read' if payment.notification_read else 'New'
        active_notifications.append({
            'id': payment.payment_id,
            'type': 'payment',
            'category': 'Payment Received',
            'title': 'Payment Received',
            'client_name': payment.client,
            'channel': 'Payment',
            'description': f"Payment confirmed via {payment.method}",
            'amount_due': payment.amount,
            'ticket_id': None,
            'sent_at': payment.created_at if hasattr(payment, 'created_at') else timezone.now(),
            'is_new': False,
            'status': payment_status,
        })

    categories = ['All'] + sorted({n['category'] for n in active_notifications})

    if search_query:
        query_lower = search_query.lower()
        active_notifications = [
            n for n in active_notifications
            if query_lower in n['title'].lower()
            or query_lower in n['client_name'].lower()
            or query_lower in n['description'].lower()
            or query_lower in n['category'].lower()
        ]

    if category_filter and category_filter != 'All':
        active_notifications = [n for n in active_notifications if n['category'] == category_filter]

    # Sort by sent_at, most recent first
    active_notifications.sort(key=lambda x: x['sent_at'], reverse=True)

    new_notifications = [n for n in active_notifications if n['status'] == 'New']
    read_notifications = [n for n in active_notifications if n['status'] != 'New']

    active_count = len(new_notifications)
    active_notifications = new_notifications[:10]
    archived_notifications = read_notifications[:50] if len(read_notifications) > 0 else []
    archived_count = len(archived_notifications)
    categories = ['All'] + sorted({n['category'] for n in active_notifications + archived_notifications})
    
    # Make badge reflect the active "New" notifications shown in the panel
    notification_count = get_admin_notification_count()
    active_count = notification_count

    context = {
        'search_query': search_query,
        'category_filter': category_filter,
        'categories': categories,
        'total_notifications': total_notifications,
        'sent_today': sent_today,
        'last_7_days': last_7_days,
        'overdue_count': overdue_count,
        'final_warning_count': final_warning_count,
        'disconnection_count': disconnection_count,
        'recent_notifications': recent_notifications,
        'recent_activities': recent_activities,
        'total_clients': total_clients,
        'active_clients': active_clients,
        'overdue_clients': overdue_clients,
        'disconnected_clients': disconnected_clients,
        'tickets_open': tickets_open,
        'notification_count': notification_count,
        'total_revenue': total_revenue,
        'monthly_revenue': monthly_revenue,
        'active_notifications': active_notifications,
        'active_count': active_count,
        'archived_notifications': archived_notifications,
        'archived_count': archived_count,
    }
    
    return render(request, 'admin/notification_dashboard.html', context)


@is_admin_view
def manage_notification_templates(request):
    """
    View to manage editable notification templates
    """
    ensure_default_notification_templates()
    templates = NotificationTemplate.objects.all().order_by('template_type', 'channel')
    context = {
        'templates': templates,
        'view': 'templates',
        'notification_count': get_admin_notification_count(),
    }
    
    return render(request, 'admin/manage_templates.html', context)


@is_admin_view
def edit_notification_template(request, template_id):
    """
    Edit a specific notification template
    """
    template = get_object_or_404(NotificationTemplate, template_id=template_id)
    
    if request.method == 'POST':
        form = NotificationTemplateForm(request.POST)
        if form.is_valid():
            # Update only the body and subject fields
            template.subject = form.cleaned_data['subject']
            template.body = form.cleaned_data['body']
            template.save()
            
            context = {
                'template': template,
                'form': form,
                'success': True,
                'message': '✓ Template updated successfully!',
                'notification_count': get_admin_notification_count(),
            }
            return render(request, 'admin/edit_template.html', context)
    else:
        # Pre-populate form with existing template data
        initial_data = {
            'template_type': template.template_type,
            'channel': template.channel,
            'subject': template.subject,
            'body': template.body,
        }
        form = NotificationTemplateForm(initial=initial_data)
    
    context = {
        'template': template,
        'form': form,
        'view': 'templates',
        'notification_count': get_admin_notification_count(),
    }
    
    return render(request, 'admin/edit_template.html', context)


@is_admin_view
def audit_log(request):
    """
    View audit log of all system activities
    """
    def build_activity_label(activity_type):
        labels = {
            'client_created': 'Client Created',
            'client_edited': 'Client Edited',
            'client_deleted': 'Client Deleted',
            'payment_recorded': 'Payment Recorded',
            'application_submitted': 'Application Submitted',
            'application_approved': 'Application Approved',
            'application_declined': 'Application Declined',
            'application_deleted': 'Application Deleted',
            'ticket_created': 'Ticket Created',
            'ticket_updated': 'Ticket Updated',
            'ticket_resolved': 'Ticket Resolved',
            'ticket_closed': 'Ticket Closed',
            'login': 'Login',
            'logout': 'Logout',
            'otp_request': 'OTP Request',
            'otp_verify': 'OTP Verify',
            'facial_enroll': 'Facial Enrollment',
            'facial_verify': 'Facial Verification',
            'fingerprint_enroll': 'Fingerprint Enrollment',
            'fingerprint_verify': 'Fingerprint Verification',
            'mfa_enable': 'MFA Enabled',
            'mfa_disable': 'MFA Disabled',
            'password_change': 'Password Changed',
            'account_lockout': 'Account Locked',
            'account_unlock': 'Account Unlocked',
            'permission_change': 'Permission Changed',
            'role_change': 'Role Changed',
            'admin_action': 'Administrative Action',
            'security_event': 'Security Event',
        }
        return labels.get(activity_type, activity_type.replace('_', ' ').title())

    combined_logs = []

    for activity in ActivityLog.objects.all().order_by('-created_at'):
        combined_logs.append({
            'time': activity.created_at,
            'activity_type': activity.activity_type,
            'activity_label': build_activity_label(activity.activity_type),
            'entity_type': activity.entity_type,
            'entity_id': activity.entity_id,
            'description': activity.description,
            'performed_by': activity.performed_by or 'System',
            'old_value': activity.old_value,
            'new_value': activity.new_value,
            'amount': activity.amount,
            'is_new': activity.is_new,
            'status': None,
            'ip_address': None,
            'user_agent': None,
            'device_info': None,
            'session_id': None,
            'error_message': None,
            'related_user': None,
            'source': 'activity',
        })

    for audit_entry in SecurityAuditLog.objects.all().order_by('-timestamp'):
        combined_logs.append({
            'time': audit_entry.timestamp,
            'activity_type': audit_entry.action_type,
            'activity_label': build_activity_label(audit_entry.action_type),
            'entity_type': 'Security',
            'entity_id': audit_entry.related_user.username if audit_entry.related_user else None,
            'description': audit_entry.description,
            'performed_by': audit_entry.user.username if audit_entry.user else 'System',
            'old_value': None,
            'new_value': None,
            'amount': None,
            'is_new': False,
            'status': audit_entry.status,
            'ip_address': audit_entry.ip_address,
            'user_agent': audit_entry.user_agent,
            'device_info': audit_entry.device_info,
            'session_id': audit_entry.session_id,
            'error_message': audit_entry.error_message,
            'related_user': audit_entry.related_user.username if audit_entry.related_user else None,
            'source': 'security',
        })

    combined_logs.sort(key=lambda entry: entry['time'], reverse=True)

    # Filtering
    filter_type = request.GET.get('type', '')
    filter_entity = request.GET.get('entity', '')
    search_query = request.GET.get('search', '').strip()

    if filter_type:
        combined_logs = [entry for entry in combined_logs if entry['activity_type'] == filter_type]

    if filter_entity:
        combined_logs = [entry for entry in combined_logs if entry['entity_type'] == filter_entity]

    if search_query:
        search_query = search_query.lower()
        combined_logs = [
            entry for entry in combined_logs
            if search_query in entry['description'].lower()
            or search_query in entry['activity_label'].lower()
            or (entry['performed_by'] and search_query in str(entry['performed_by']).lower())
            or (entry['ip_address'] and search_query in str(entry['ip_address']).lower())
        ]

    # Pagination
    from django.core.paginator import Paginator
    paginator = Paginator(combined_logs, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    new_logs_count = ActivityLog.objects.filter(is_new=True).count()

    context = {
        'page_obj': page_obj,
        'logs': page_obj.object_list,
        'new_logs_count': new_logs_count,
        'notification_count': get_admin_notification_count(),
        'view': 'audit-log',
    }

    return render(request, 'admin/audit_log.html', context)


@is_admin_view
def mark_notification_read(request):
    """
    Mark a notification as read so it persists.
    """
    if request.method == 'POST':
        import json
        try:
            data = json.loads(request.body)
            notification_id = data.get('notification_id')
            notification_type = data.get('notification_type')

            if notification_type in ('sms', 'email', 'overdue'):
                OverdueNotification.objects.filter(notification_id=notification_id).update(notification_read=True)
            elif notification_type == 'ticket':
                Ticket.objects.filter(ticket_id=notification_id).update(notification_read=True)
            elif notification_type == 'ticket_activity':
                ActivityLog.objects.filter(activity_id=notification_id).update(is_new=False)
            elif notification_type == 'payment':
                Payment.objects.filter(payment_id=notification_id).update(notification_read=True)
            else:
                return JsonResponse({'success': False, 'message': 'Unknown notification type'}, status=400)

            return JsonResponse({'success': True, 'message': 'Notification marked as read'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=400)

    return JsonResponse({'success': False, 'message': 'Invalid request'}, status=400)


@is_admin_view
def delete_notification(request):
    """
    Delete a notification from archive
    """
    if request.method == 'POST':
        import json
        try:
            data = json.loads(request.body)
            notification_id = data.get('notification_id')
            notification_type = data.get('notification_type')
            
            if notification_type in ('sms', 'email', 'overdue'):
                OverdueNotification.objects.filter(notification_id=notification_id).update(hide_from_notifications=True)
            elif notification_type == 'ticket':
                Ticket.objects.filter(ticket_id=notification_id).update(hide_from_notifications=True)
            elif notification_type == 'ticket_activity':
                ActivityLog.objects.filter(activity_id=notification_id).update(is_new=False)
            elif notification_type == 'payment':
                Payment.objects.filter(payment_id=notification_id).update(hide_from_notifications=True)
            
            return JsonResponse({'success': True, 'message': 'Notification deleted'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=400)
    
    return JsonResponse({'success': False, 'message': 'Invalid request'}, status=400)
