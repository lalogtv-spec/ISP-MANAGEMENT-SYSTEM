from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout, authenticate, login
from django.contrib import messages
from django.core import signing
from django.http import JsonResponse
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.views.decorators.cache import never_cache
import calendar
from django.utils import timezone
from django.db.models import Q, Case, When, IntegerField
from api.models import ActivityLog, Client, Payment, Ticket, Application, ApplicationDecision, NotificationSettings, OverdueNotification
from api.gcash_service import GCashService
from api.stripe_service import StripeService
from api.notification_service import NotificationService
from api.models import PaymentMethod
from dashboard.forms import NotificationSettingsForm
from security.models import BiometricData, MFASettings, AuditLog, UserSecurityProfile
from security.otp_service import OTPService
from security.mfa_service import MFAService
from security.fingerprint_auth import FingerprintAuthService
from security.audit_logs import AuditLogger
from security.webauthn import (
    b64url_decode,
    b64url_encode,
    cose_key_to_public_key,
    decode_cbor,
    parse_authenticator_data,
    parse_client_data,
    verify_webauthn_assertion,
)
from datetime import date, timedelta, datetime
from django.conf import settings
from decimal import Decimal
from io import BytesIO
import base64
import hashlib
import json
import secrets
import uuid
from django.template.loader import render_to_string
from django.urls import reverse
import traceback


def _get_plan_fee(plan):
    plan_fees = {
        'Basic': 499.00,
        'Standard': 799.00,
        'Premium': 1299.00,
        'Basic 25Mbps': 499.00,
        'Standard 50Mbps': 799.00,
        'Premium 100Mbps': 1299.00,
    }
    return plan_fees.get(plan, 499.00)


def _ensure_client_for_user(user):
    """Return the linked client, creating it from an approved application if needed."""
    client = Client.objects.filter(email=user.email).first()
    if client:
        return client

    app = Application.objects.filter(
        Q(user=user) | Q(email=user.email),
        status='Approved'
    ).order_by('-created_at').first()
    if not app:
        return None

    plan_fee = _get_plan_fee(app.plan)
    client_id = None
    counter = Client.objects.count() + 1
    while client_id is None:
        candidate = f'C{str(counter).zfill(3)}'
        if not Client.objects.filter(client_id=candidate).exists():
            client_id = candidate
        else:
            counter += 1

    client = Client.objects.create(
        client_id=client_id,
        name=app.name,
        email=app.email,
        phone=app.phone,
        address=app.address,
        plan=app.plan,
        fee=plan_fee,
        status='Active',
        due_date=date.today() + timedelta(days=30),
        balance=plan_fee,
        joined=date.today()
    )
    return client


def _generate_payment_id():
    """Generate a short unique payment ID that fits the model length."""
    while True:
            payment_id = f"PAY{uuid.uuid4().hex[:7].upper()}"
            if not Payment.objects.filter(payment_id=payment_id).exists():
                return payment_id


def _generate_ticket_id():
    """Generate a short unique ticket ID that fits the model length."""
    while True:
        ticket_id = f"TKT{uuid.uuid4().hex[:7].upper()}"
        if not Ticket.objects.filter(ticket_id=ticket_id).exists():
            return ticket_id


def _add_months(start_date, months):
    """Add months to a date while keeping the day within the target month."""
    month = start_date.month - 1 + months
    year = start_date.year + month // 12
    month = month % 12 + 1
    day = min(start_date.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _calculate_service_end_date(client):
    """Project the service end date from the current due date and verified payments."""
    if not client:
        return None

    service_end_date = client.due_date
    monthly_fee = Decimal(str(client.fee)) if getattr(client, 'fee', None) is not None else Decimal('0.00')

    if monthly_fee <= 0:
        return service_end_date

    verified_payments = Payment.objects.filter(client=client.name, status='Verified').order_by('date', 'created_at')
    for payment in verified_payments:
        try:
            months_covered = int(Decimal(str(payment.amount)) // monthly_fee)
        except Exception:
            months_covered = 0

        if months_covered >= 1:
            projected_end_date = _add_months(payment.date, months_covered)
            if projected_end_date > service_end_date:
                service_end_date = projected_end_date

    return service_end_date


def _apply_payment_coverage(client, payment_amount, months_override=None):
    """Apply a payment amount to the client's balance and service coverage."""
    if not client:
        return client

    if client.balance is None:
        client.balance = Decimal('0.00')

    payment_amount = Decimal(str(payment_amount))
    current_balance = Decimal(str(client.balance))
    client.balance = max(current_balance - payment_amount, Decimal('0.00'))

    if months_override is not None:
        months_covered = int(months_override)
    else:
        try:
            monthly_fee = Decimal(str(client.fee))
            months_covered = int(payment_amount // monthly_fee) if monthly_fee > 0 else 0
        except Exception:
            months_covered = 0

    if months_covered >= 1:
        start_date = client.due_date if client.due_date and client.due_date > date.today() else date.today()
        client.due_date = _add_months(start_date, months_covered)

    client.save()
    return client


def _decode_data_url(data_url):
    """Decode a data URL or raw base64 string into bytes."""
    if not data_url:
        return None
    if ',' in data_url:
        data_url = data_url.split(',', 1)[1]
    try:
        return base64.b64decode(data_url)
    except Exception:
        return None


def _get_security_level(user, security_profile, mfa_settings, facial_enrolled, fingerprint_enrolled):
    score = 1
    if security_profile:
        score += 1 if security_profile.mfa_enabled else 0
        score += 1 if security_profile.facial_data_enrolled else 0
        score += 1 if security_profile.fingerprint_enrolled else 0
    if mfa_settings and mfa_settings.is_enabled:
        score += 1
        if mfa_settings.require_biometric_for_sensitive_actions:
            score += 1
        if mfa_settings.require_on_every_login:
            score += 1
    if facial_enrolled:
        score += 1
    if fingerprint_enrolled:
        score += 1

    if score >= 6:
        return {'label': 'Strong', 'color': 'emerald', 'score': 92}
    if score >= 4:
        return {'label': 'Moderate', 'color': 'amber', 'score': 68}
    return {'label': 'Basic', 'color': 'rose', 'score': 35}


def _get_biometric_status(user):
    security_profile, _ = UserSecurityProfile.objects.get_or_create(user=user)
    facial_records = BiometricData.objects.filter(user=user, biometric_type='facial', is_active=True).order_by('-updated_at', '-enrolled_at')
    fingerprint_records = BiometricData.objects.filter(user=user, biometric_type='fingerprint', is_active=True).order_by('-updated_at', '-enrolled_at')
    mobile_passkey_records = BiometricData.objects.filter(user=user, biometric_type='mobile_passkey', is_active=True).order_by('-updated_at', '-enrolled_at')
    facial = facial_records.first()
    fingerprint = fingerprint_records.first()
    mobile_passkey = mobile_passkey_records.first()

    has_face = facial is not None
    has_fingerprint = fingerprint is not None
    has_mobile_passkey = mobile_passkey is not None

    if not has_face and not has_fingerprint and not has_mobile_passkey:
        status = 'Not Registered'
        detail = 'Biometrics Not Set Up'
        badge = 'rose'
    elif has_face and has_fingerprint and has_mobile_passkey:
        status = 'Fully Registered'
        detail = 'All biometric methods are active'
        badge = 'emerald'
    else:
        status = 'Partially Registered'
        detail = 'Complete biometric setup available'
        badge = 'amber'

    last_update = None
    if facial and fingerprint and mobile_passkey:
        last_update = max(facial.updated_at, fingerprint.updated_at, mobile_passkey.updated_at)
    elif facial and fingerprint:
        last_update = max(facial.updated_at, fingerprint.updated_at)
    elif facial and mobile_passkey:
        last_update = max(facial.updated_at, mobile_passkey.updated_at)
    elif fingerprint and mobile_passkey:
        last_update = max(fingerprint.updated_at, mobile_passkey.updated_at)
    elif facial:
        last_update = facial.updated_at
    elif fingerprint:
        last_update = fingerprint.updated_at
    elif mobile_passkey:
        last_update = mobile_passkey.updated_at
    else:
        last_update = security_profile.updated_at

    method_count = sum([has_face, has_fingerprint, has_mobile_passkey])
    progress = method_count / 3.0

    return {
        'status': status,
        'detail': detail,
        'badge': badge,
        'has_face': has_face,
        'has_fingerprint': has_fingerprint,
        'has_mobile_passkey': has_mobile_passkey,
        'facial_count': facial_records.count(),
        'fingerprint_count': fingerprint_records.count(),
        'mobile_passkey_count': mobile_passkey_records.count(),
        'complete': has_face and has_fingerprint and has_mobile_passkey,
        'method_count': method_count,
        'progress': progress,
        'facial': facial,
        'fingerprint': fingerprint,
        'mobile_passkey': mobile_passkey,
        'last_update': last_update,
        'status_slug': status.lower().replace(' ', '-'),
    }


def _get_notification_badge_count(client):
    """Calculate the count of new notifications for the header badge (matches notifications view)."""
    if not client:
        return 0
    
    from api.notification_service import NotificationService
    
    days_overdue = 0
    if client.due_date:
        days_overdue = (timezone.now().date() - client.due_date).days
    
    # Get all overdue notifications
    overdue_notifications = OverdueNotification.objects.filter(
        client=client.client_id,
        hide_from_notifications=False
    ).order_by('-sent_at')
    
    # Build all notifications like the client_notifications view does
    all_notifications = []
    for n in overdue_notifications:
        all_notifications.append({
            'status': 'New',
            'notification_type': n.notification_type,
        })
    
    # Add ticket activities
    ticket_activities = ActivityLog.objects.filter(
        entity_type='Ticket',
        entity_name=client.name,
        activity_type__in=[
            'ticket_created',
            'ticket_scheduled',
            'ticket_updated',
            'ticket_resolved',
            'ticket_closed',
            'ticket_reschedule_requested',
        ],
    ).order_by('-created_at')
    
    for activity in ticket_activities:
        all_notifications.append({
            'status': 'Read' if not activity.is_new else 'New',
            'notification_type': 'Ticket',
        })
    
    # Add current overdue notice if applicable
    if days_overdue > 0:
        current_notice_type = NotificationService.get_notification_type(days_overdue)
        has_matching_notice = any(
            item.get('notification_type') == current_notice_type for item in all_notifications
        )
        if not has_matching_notice:
            all_notifications.append({
                'status': 'New',
                'notification_type': current_notice_type,
            })
    
    # Count only "New" notifications
    active_notifications = [n for n in all_notifications if n.get('status', 'New') == 'New']
    return len(active_notifications)


def _biometric_prompt_needed(request, biometric_status):
    dismissed = request.session.get('biometric_prompt_dismissed', False)
    return not biometric_status['complete'] and not dismissed and biometric_status.get('progress', 0) <= 0.5


def _security_context(request, user, security_profile=None):
    security_profile = security_profile or UserSecurityProfile.objects.get_or_create(user=user)[0]
    mfa_settings, _ = MFASettings.objects.get_or_create(user=user)
    biometric_status = _get_biometric_status(user)
    security_level = _get_security_level(
        user,
        security_profile,
        mfa_settings,
        biometric_status['has_face'],
        biometric_status['has_fingerprint']
    )
    if biometric_status['has_mobile_passkey']:
        security_level = {
            'label': security_level['label'],
            'color': security_level['color'],
            'score': min(security_level['score'] + 8, 100),
        }
    return {
        'biometric_status': biometric_status,
        'biometric_prompt_needed': _biometric_prompt_needed(request, biometric_status),
        'security_level': security_level,
        'mfa_settings': mfa_settings,
        'security_profile': security_profile,
        'facial_data': biometric_status['facial'],
        'fingerprint_data': biometric_status['fingerprint'],
        'mobile_passkey_data': biometric_status['mobile_passkey'],
        'facial_count': biometric_status['facial_count'],
        'fingerprint_count': biometric_status['fingerprint_count'],
        'mobile_passkey_count': biometric_status['mobile_passkey_count'],
        'last_biometric_update': biometric_status['last_update'],
        # (no urgent_count here) header count is controlled per-view to match UI
    }


def _remember_security_form_state(request, **values):
    """Persist a small amount of security form state across redirects."""
    cleaned = {key: (value or '') for key, value in values.items()}
    request.session['security_form_state'] = cleaned
    request.session.modified = True


def _pop_security_form_state(request):
    """Return and clear preserved security form state."""
    return request.session.pop('security_form_state', {})


def _coerce_fingerprint_payload(raw_value):
    """
    Normalize fingerprint payloads from browser forms or bridge apps.
    Accepts both JSON strings and raw bytes of fingerprint/WebAuthn data.
    """
    if not raw_value:
        return None
    if hasattr(raw_value, 'read'):
        return raw_value.read()
    if isinstance(raw_value, dict):
        return raw_value
    if isinstance(raw_value, (bytes, bytearray)):
        return raw_value
    if isinstance(raw_value, str):
        raw_value = raw_value.strip()
        if not raw_value:
            return None
        try:
            return json.loads(raw_value)
        except json.JSONDecodeError:
            return raw_value
    return raw_value


def _mobile_passkey_rp_id(request):
    host = request.get_host().split(':', 1)[0]
    return host


def _mobile_passkey_origin(request):
    scheme = request.META.get('HTTP_X_FORWARDED_PROTO', request.scheme)
    return f'{scheme}://{request.get_host()}'


def _browser_webauthn_context(request, prefix):
    """
    Capture the browser-facing host/origin so WebAuthn works through tunnels
    and reverse proxies.
    """
    rp_id = (request.GET.get('rp_id') or request.POST.get('rp_id') or '').strip().lower()
    origin = (request.GET.get('origin') or request.POST.get('origin') or '').strip().rstrip('/')

    if not rp_id:
        rp_id = request.get_host().split(':', 1)[0]
    if not origin:
        origin = _mobile_passkey_origin(request)

    request.session[f'{prefix}_rp_id'] = rp_id
    request.session[f'{prefix}_origin'] = origin
    request.session.modified = True
    return rp_id, origin


def _get_mobile_passkey(user):
    return BiometricData.objects.filter(
        user=user,
        biometric_type='mobile_passkey',
        is_active=True
    ).first()


def _format_webauthn_response_for_fingerprint(mobile_passkey_data):
    """
    Format mobile passkey data as WebAuthn response for real biometric enrollment.
    Extracts actual device biometric credentials (credential_id, public_key) from stored passkey.

    Args:
        mobile_passkey_data (dict): Template data from BiometricData.template_data

    Returns:
        dict: Formatted for FingerprintAuthService with real biometric verification
    """
    return {
        'source': 'mobile_passkey',
        'credential_id': mobile_passkey_data.get('credential_id', ''),
        'public_key': mobile_passkey_data.get('public_key', {}),
        'sign_count': mobile_passkey_data.get('sign_count', 0),
    }


@never_cache
@login_required
def client_dashboard(request):
    """Client dashboard with account overview"""
    client = Client.objects.filter(email=request.user.email).first()
    if not client:
        client = _ensure_client_for_user(request.user)

    # If there still is no client record, keep the user in the application flow.
    try:
        if not client:
            decision = ApplicationDecision.objects.filter(
                Q(user=request.user) | Q(email=request.user.email)
            ).order_by('-created_at').first()
            if decision:
                if decision.status != 'Approved':
                    return redirect('dashboard:application-status', app_id=decision.app_id)
            else:
                application = Application.objects.filter(user=request.user).latest('created_at')
                if application.status != 'Approved':
                    return redirect('dashboard:application-status', app_id=application.app_id)
    except Application.DoesNotExist:
        if not client:
            return redirect('dashboard:new_application')
    
    # Get notification badge count (uses same logic as notifications view)
    urgent_count = _get_notification_badge_count(client)
    
    recent_payments = Payment.objects.filter(client=client).order_by('-date')[:3] if client else []
    recent_tickets = Ticket.objects.filter(client=client).order_by('-created')[:3] if client else []
    
    context = {
        'view': 'dashboard',
        'client': client,
        'recent_payments': recent_payments,
        'recent_tickets': recent_tickets,
        'urgent_count': urgent_count,
    }
    context.update(_security_context(request, request.user))
    
    return render(request, 'client/dashboard.html', context)


@never_cache
@login_required
def client_account(request):
    """Client account details page"""
    client = _ensure_client_for_user(request.user)
    
    # Get notification badge count (uses same logic as notifications view)
    urgent_count = _get_notification_badge_count(client)
    
    context = {
        'view': 'account',
        'client': client,
        'urgent_count': urgent_count,
    }
    context.update(_security_context(request, request.user))
    
    return render(request, 'client/account.html', context)


@never_cache
@login_required
def client_payments(request):
    """Client payment history"""
    client = _ensure_client_for_user(request.user)
    
    # Get notification badge count (uses same logic as notifications view)
    urgent_count = _get_notification_badge_count(client)
    
    service_duration = None
    if client:
        payments = Payment.objects.filter(client=client).order_by('-date')
        verified_payments = payments.filter(status='Verified')
        total_paid = sum(p.amount for p in verified_payments)
        pending_amount = client.balance

        service_end_date = _calculate_service_end_date(client)

        if service_end_date:
            try:
                days_remaining = (service_end_date - timezone.now().date()).days
            except Exception:
                days_remaining = None

            if days_remaining is None:
                service_duration = 'Due date information unavailable'
            elif days_remaining > 1:
                service_duration = f'{days_remaining} days left until service ends ({service_end_date.strftime("%b %d, %Y")})'
            elif days_remaining == 1:
                service_duration = '1 day left until service ends'
            elif days_remaining == 0:
                service_duration = 'Service ends today'
            else:
                service_duration = f'Service ended {abs(days_remaining)} days ago'
        else:
            service_duration = 'Due date not set'
        service_end_date_iso = service_end_date.isoformat() if service_end_date else None
    else:
        payments = Payment.objects.none()
        total_paid = 0
        pending_amount = 0
        service_end_date = None
        service_end_date_iso = None

    context = {
        'view': 'payments',
        'client': client,
        'payment_methods': [],
        'payments': payments,
        'total_paid': total_paid,
        'pending_amount': pending_amount,
        'service_duration': service_duration,
        'service_end_date': service_end_date,
        'service_end_date_iso': service_end_date_iso,
        'urgent_count': urgent_count,
    }
    context.update(_security_context(request, request.user))
    
    return render(request, 'client/payments.html', context)


@never_cache
@login_required
@require_http_methods(["GET", "POST"])
def client_payment_methods_api(request):
    """API to list and create payment methods for the logged-in client's account."""
    client = _ensure_client_for_user(request.user)
    if not client:
        return JsonResponse({'error': 'client_not_found'}, status=400)

    if request.method == 'GET':
        methods = PaymentMethod.objects.filter(client=client).order_by('-created_at')
        data = []
        for m in methods:
            data.append({
                'id': str(m.id),
                'displayName': m.display_name,
                'detail': m.detail,
                'brand': m.brand,
                'verified': m.verified,
                'default': m.default,
            })
        return JsonResponse({'methods': data})

    # POST - create
    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except Exception:
        payload = {}

    display = payload.get('displayName') or payload.get('display_name') or 'Method'
    detail = payload.get('detail') or ''
    brand = payload.get('brand') or ''
    verified = bool(payload.get('verified'))
    is_default = bool(payload.get('default'))

    if is_default:
        PaymentMethod.objects.filter(client=client).update(default=False)

    m = PaymentMethod.objects.create(
        client=client,
        display_name=display,
        detail=detail,
        brand=brand,
        verified=verified,
        default=is_default,
    )

    return JsonResponse({'method': {
        'id': str(m.id), 'displayName': m.display_name, 'detail': m.detail, 'brand': m.brand, 'verified': m.verified, 'default': m.default
    }}, status=201)


@never_cache
@login_required
@require_http_methods(["PUT", "DELETE"])
def client_payment_method_detail(request, method_id):
    client = _ensure_client_for_user(request.user)
    if not client:
        return JsonResponse({'error': 'client_not_found'}, status=400)

    try:
        m = PaymentMethod.objects.get(id=method_id, client=client)
    except PaymentMethod.DoesNotExist:
        return JsonResponse({'error': 'not_found'}, status=404)

    if request.method == 'DELETE':
        m.delete()
        return JsonResponse({'ok': True})

    # PUT - update
    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except Exception:
        payload = {}

    m.display_name = payload.get('displayName', payload.get('display_name', m.display_name))
    m.detail = payload.get('detail', m.detail)
    m.brand = payload.get('brand', m.brand)
    m.verified = bool(payload.get('verified', m.verified))
    new_default = bool(payload.get('default', m.default))
    if new_default:
        PaymentMethod.objects.filter(client=client).update(default=False)
    m.default = new_default
    m.save()
    return JsonResponse({'method': {'id': str(m.id), 'displayName': m.display_name, 'detail': m.detail, 'brand': m.brand, 'verified': m.verified, 'default': m.default}})


@never_cache
@login_required
def client_tickets(request):
    """Client support tickets"""
    client = _ensure_client_for_user(request.user)
    
    # Get notification badge count (uses same logic as notifications view)
    urgent_count = _get_notification_badge_count(client)
    
    if client:
        status_order = Case(
            When(status='Pending', then=0),
            When(status='Scheduled', then=1),
            When(status='In Progress', then=2),
            When(status='Resolved', then=3),
            default=4,
            output_field=IntegerField(),
        )
        tickets = Ticket.objects.filter(client=client).order_by(status_order, '-created')
        total_tickets = tickets.count()
        pending_tickets = tickets.filter(status='Pending').count()
        open_tickets = tickets.filter(status__in=['Pending', 'In Progress']).count()
        in_progress_tickets = tickets.filter(status='In Progress').count()
        resolved_tickets = tickets.filter(status='Resolved').count()
        reschedule_requested_ticket_ids = set(
            ActivityLog.objects.filter(
                entity_type='Ticket',
                activity_type='ticket_reschedule_requested',
                entity_id__in=tickets.values_list('ticket_id', flat=True),
            ).values_list('entity_id', flat=True).distinct()
        )
        # Find the next scheduled ticket (if any) to show a client-facing notice
        scheduled_ticket = tickets.filter(scheduled_date__isnull=False).exclude(status__in=['Resolved', 'Closed']).order_by('scheduled_date').first()
    else:
        tickets = Ticket.objects.none()
        total_tickets = 0
        pending_tickets = 0
        open_tickets = 0
        in_progress_tickets = 0
        resolved_tickets = 0
        reschedule_requested_ticket_ids = set()
        scheduled_ticket = None
    
    context = {
        'view': 'tickets',
        'client': client,
        'tickets': tickets,
        'total_tickets': total_tickets,
        'pending_tickets': pending_tickets,
        'open_tickets': open_tickets,
        'in_progress_tickets': in_progress_tickets,
        'resolved_tickets': resolved_tickets,
        'urgent_count': urgent_count,
        'scheduled_ticket': scheduled_ticket,
        'reschedule_requested_ticket_ids': reschedule_requested_ticket_ids,
    }
    context.update(_security_context(request, request.user))
    
    return render(request, 'client/tickets.html', context)


@login_required
def client_ticket_create(request):
    """Create a new support ticket for the logged-in client."""
    client = _ensure_client_for_user(request.user)
    if not client:
        messages.error(request, 'Client profile not found yet. Please contact support.')
        return redirect('dashboard:client-tickets')

    char_limit = 250
    is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest'

    # Check if client has unresolved tickets
    unresolved_count = Ticket.objects.filter(
        client=client.name,
        status__in=['Pending', 'In Progress', 'Scheduled']
    ).count()
    
    if request.method == 'POST':
        if unresolved_count > 0:
            error_message = f'You have {unresolved_count} unresolved ticket(s). Please resolve them before creating a new one.'
            if is_ajax:
                return JsonResponse({'success': False, 'error': error_message}, status=400)
            messages.error(request, error_message)
        else:
            category = request.POST.get('category', '').strip()
            description = request.POST.get('description', '').strip()
            attachment = request.FILES.get('attachment')

            if not category or not description:
                error_message = 'Please provide both a problem and a description for your ticket.'
                if is_ajax:
                    return JsonResponse({'success': False, 'error': error_message}, status=400)
                messages.error(request, error_message)
            elif len(description) > char_limit:
                error_message = f'Description must be {char_limit} characters or fewer.'
                if is_ajax:
                    return JsonResponse({'success': False, 'error': error_message}, status=400)
                messages.error(request, error_message)
            else:
                priority_map = {
                    'Service Outage': 'Critical',
                    'Payment Issue': 'High',
                    'Technical Support': 'High',
                    'Billing Question': 'Medium',
                    'Other': 'Low',
                }
                priority = priority_map.get(category, 'Low')
                Ticket.objects.create(
                    ticket_id=_generate_ticket_id(),
                    client=client.name,
                    category=category,
                    priority=priority,
                    status='Pending',
                    description=description,
                    attachment=attachment,
                    assigned='Unassigned',
                    created=date.today(),
                )
                if is_ajax:
                    return JsonResponse({
                        'success': True,
                        'message': 'Your ticket has been submitted successfully.',
                        'redirect': reverse('dashboard:client-tickets'),
                    })
                messages.success(request, 'Your ticket has been submitted successfully.')
                return redirect('dashboard:client-tickets')

    context = {
        'view': 'tickets',
        'client': client,
        'unresolved_count': unresolved_count,
        'urgent_count': 0,
    }
    context.update(_security_context(request, request.user))
    return render(request, 'client/ticket_form.html', context)


@login_required
def client_ticket_reschedule(request, ticket_id):
    """Allow a client to request a reschedule for a ticket."""
    client = _ensure_client_for_user(request.user)
    if not client:
        messages.error(request, 'Client profile not found yet. Please contact support.')
        return redirect('dashboard:client-tickets')

    ticket = Ticket.objects.filter(ticket_id=ticket_id, client=client.name).first()
    if not ticket:
        messages.error(request, 'Ticket not found or you do not have permission.')
        return redirect('dashboard:client-tickets')

    reschedule_locked = ActivityLog.objects.filter(
        entity_type='Ticket',
        entity_id=ticket.ticket_id,
        activity_type='ticket_reschedule_requested',
    ).exists()

    error = None
    is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest'
    if request.method == 'POST':
        if reschedule_locked:
            if is_ajax:
                return JsonResponse({'success': False, 'error': 'This ticket has already used its one reschedule request.'}, status=400)
            messages.error(request, 'This ticket has already used its one reschedule request. Please contact support for any further changes.')
            return redirect('dashboard:client-tickets')

        new_date = request.POST.get('scheduled', '').strip()
        new_time = request.POST.get('scheduled_time', '').strip()
        reason = request.POST.get('reason', '').strip()
        if len(reason) > 150:
            error = 'Reason must be 150 characters or fewer.'
        elif not new_date or not new_time:
            error = 'Please choose a date and time.'
            if is_ajax:
                return JsonResponse({'success': False, 'error': error}, status=400)
        else:
            try:
                # Parse requested schedule but do not apply it yet.
                def _parse_date_str(s):
                    s = s.strip()
                    if not s:
                        raise ValueError('empty')
                    # Try ISO first
                    try:
                        return datetime.strptime(s, '%Y-%m-%d').date()
                    except Exception:
                        pass
                    # Try common human formats: 'Jun 16', 'June 16', with optional year
                    current_year = datetime.now().year
                    candidates = [s, f"{s}, {current_year}"]
                    for cand in candidates:
                        for fmt in ('%b %d, %Y', '%B %d, %Y', '%b %d', '%B %d'):
                            try:
                                dt = datetime.strptime(cand, fmt)
                                # If no year in format, ensure year is current
                                if '%Y' not in fmt:
                                    dt = dt.replace(year=current_year)
                                return dt.date()
                            except Exception:
                                continue
                    # As a last resort, try parsing with common separators
                    try:
                        cleaned = s.replace('/', ' ').replace('-', ' ').replace('.', ' ')
                        parts = cleaned.split()
                        if len(parts) >= 2:
                            # Try 'Jun 16' style
                            month_part = parts[0]
                            day_part = parts[1].rstrip(',')
                            cand = f"{month_part} {day_part}, {current_year}"
                            return datetime.strptime(cand, '%b %d, %Y').date()
                    except Exception:
                        pass
                    raise ValueError('unrecognized date format')

                def _parse_time_str(s):
                    s = s.strip()
                    if not s:
                        raise ValueError('empty')
                    for fmt in ('%H:%M', '%I:%M %p', '%I:%M%p'):
                        try:
                            return datetime.strptime(s, fmt).time()
                        except Exception:
                            continue
                    # Accept values like '8:30' without AM/PM as 24h
                    try:
                        return datetime.strptime(s, '%H:%M').time()
                    except Exception:
                        pass
                    raise ValueError('unrecognized time format')

                requested_date = _parse_date_str(new_date)
                requested_time_obj = _parse_time_str(new_time)

                # Format time as AM/PM for display
                formatted_time = requested_time_obj.strftime('%I:%M %p')

                # Record a reschedule request in activity log for admin approval.
                # Do not send an email now; only notify once the admin approves the request.
                ActivityLog.objects.create(
                    activity_type='ticket_reschedule_requested',
                    entity_type='Ticket',
                    entity_id=ticket.ticket_id,
                    entity_name=ticket.client,
                    description=f'Client requested reschedule to {requested_date.strftime("%b %d, %Y")} at {formatted_time}. Reason: {reason}',
                    old_value=str({'scheduled_date': str(ticket.scheduled_date), 'scheduled_time': str(ticket.scheduled_time), 'status': ticket.status}),
                    new_value=str({'requested_date': str(requested_date), 'requested_time': str(requested_time_obj), 'reason': reason}),
                    performed_by=request.user.username if request.user and request.user.is_authenticated else 'Client',
                )
                if is_ajax:
                    return JsonResponse({'success': True, 'message': 'Your reschedule request has been submitted. The team will review and confirm.'})
                messages.success(request, 'Your reschedule request has been submitted. The team will review and confirm.')
                return redirect('dashboard:client-tickets')
            except ValueError:
                error = 'Invalid date/time format.'
                if is_ajax:
                    return JsonResponse({'success': False, 'error': error}, status=400)

    context = {
        'view': 'tickets',
        'client': client,
        'ticket': ticket,
        'error': error,
        'reschedule_locked': reschedule_locked,
    }
    context.update(_security_context(request, request.user))
    return render(request, 'client/ticket_reschedule.html', context)


@login_required
def process_payment(request):
    """Process payment immediately: create Payment record, update balance, send receipt"""
    if request.method != 'POST':
        return redirect('dashboard:client-payments')
    
    client = _ensure_client_for_user(request.user)
    if not client:
        return redirect('dashboard:client-payments')
    
    try:
        payment_type = request.POST.get('payment_type', 'current')
        amount = float(request.POST.get('amount', 0))
        months = int(request.POST.get('months', 1))
        method = request.POST.get('method', 'GCash')
        
        if amount <= 0:
            messages.error(request, 'Invalid payment amount')
            return redirect('dashboard:client-payments')
        
        # Create payment record with "Verified" status
        payment_id = _generate_payment_id()
        payment = Payment.objects.create(
            payment_id=payment_id,
            client=client.name,
            date=date.today(),
            amount=Decimal(str(amount)),
            period=f"{months} month(s)" if payment_type == 'advance' else 'Current month',
            method=method,
            status='Verified'
        )
        
        # Apply payment to client balance
        _apply_payment_coverage(client, amount, months_override=months)
        
        # Send email receipt
        try:
            subject = f"Payment Receipt - ₱{amount:.2f} - NetConnect ISP"
            html_message = f"""
            <h2>Payment Receipt</h2>
            <p>Hi {client.name},</p>
            <p>Your payment has been successfully processed.</p>
            
            <div style="background-color: #f5f5f5; padding: 15px; border-radius: 5px; margin: 20px 0;">
                <p><strong>Reference ID:</strong> {payment_id}</p>
                <p><strong>Amount Paid:</strong> ₱{amount:.2f}</p>
                <p><strong>Payment Method:</strong> {method}</p>
                <p><strong>Payment Type:</strong> {"Advance" if payment_type == "advance" else "Current Month"}</p>
                <p><strong>Months Covered:</strong> {months}</p>
                <p><strong>Date:</strong> {date.today().strftime('%B %d, %Y')}</p>
                <p><strong>New Service End Date:</strong> {client.due_date.strftime('%B %d, %Y')}</p>
            </div>
            
            <p>Thank you for your payment!</p>
            <p>NetConnect ISP Support Team</p>
            """
            
            from django.core.mail import send_mail
            send_mail(
                subject,
                f"Payment Receipt - ₱{amount:.2f}",
                settings.DEFAULT_FROM_EMAIL,
                [client.email],
                html_message=html_message,
                fail_silently=True
            )
        except Exception as e:
            print(f"Email sending error: {e}")
        
        messages.success(request, f'Payment of ₱{amount:.2f} processed successfully via {method}!')
        return redirect('dashboard:client-payments')
    
    except (ValueError, TypeError) as e:
        messages.error(request, f'Payment processing error: {str(e)}')
        return redirect('dashboard:client-payments')


@login_required
def gcash_payment(request):
    """Show GCash payment form with two fixed payment options"""
    client = _ensure_client_for_user(request.user)
    if not client:
        return render(request, 'client/payments.html', {
            'view': 'payments',
            'client': None,
            'payments': Payment.objects.none(),
            'total_paid': 0,
            'pending_amount': 0,
            'urgent_count': 0,
            'error': 'Client profile not found yet. Please contact support to activate online payments.',
        })
    
    # Use client's fee directly (which is already set when client is created)
    plan_fee = float(client.fee)
    
    # Handle GET request with payment parameters (direct payment processing)
    if request.method == 'GET' and request.GET.get('payment_type'):
        payment_type = request.GET.get('payment_type', 'current')
        amount = float(request.GET.get('amount', 0))
        months = int(request.GET.get('months', 1))
        
        try:
            if amount <= 0:
                raise ValueError("Invalid payment amount")
            
            # Determine payment description
            if payment_type == 'current':
                description = f"Current month payment - {client.name} ({client.plan})"
            elif payment_type == 'advance':
                description = f"Advance payment for {months} month(s) - {client.name} ({client.plan})"
            else:
                raise ValueError("Invalid payment type")
            
            # Create GCash payment link
            callback_url = request.build_absolute_uri('/client/gcash-callback/')
            payment_response = GCashService.create_payment_link(
                client_email=client.email,
                amount=amount,
                description=description,
                callback_url=callback_url
            )
            
            if payment_response['success']:
                # Redirect to GCash payment link
                return redirect(payment_response['payment_link'])
            else:
                raise ValueError(payment_response.get('error', 'Payment creation failed'))
        
        except (ValueError, TypeError) as e:
            context = {
                'view': 'payments',
                'client': client,
                'error': str(e),
                'pending_amount': client.balance,
                'plan_fee': plan_fee,
                'month_prices': {
                    1: plan_fee * 1,
                    2: plan_fee * 2,
                    3: plan_fee * 3,
                    6: plan_fee * 6,
                    12: plan_fee * 12,
                }
            }
            return render(request, 'client/gcash_payment.html', context)
    
    if request.method == 'POST':
        payment_type = request.POST.get('payment_type', 'current')
        amount = float(request.POST.get('amount', 0))
        
        try:
            # Validate amount is not empty
            if amount <= 0:
                raise ValueError("Invalid payment amount")
            
            # Determine payment description
            if payment_type == 'current':
                description = f"Current month payment - {client.name} ({client.plan})"
            elif payment_type == 'advance':
                months = int(request.POST.get('months', 1))
                description = f"Advance payment for {months} month(s) - {client.name} ({client.plan})"
            else:
                raise ValueError("Invalid payment type")
            
            # Create GCash payment link
            callback_url = request.build_absolute_uri('/client/gcash-callback/')
            payment_response = GCashService.create_payment_link(
                client_email=client.email,
                amount=amount,
                description=description,
                callback_url=callback_url
            )
            
            if payment_response['success']:
                # Redirect to GCash payment link
                return redirect(payment_response['payment_link'])
            else:
                error_msg = payment_response.get('error', 'Payment creation failed')
                context = {
                    'view': 'payments',
                    'client': client,
                    'error': error_msg,
                    'pending_amount': client.balance,
                    'plan_fee': plan_fee,
                    'month_prices': {
                        1: plan_fee * 1,
                        2: plan_fee * 2,
                        3: plan_fee * 3,
                        6: plan_fee * 6,
                        12: plan_fee * 12,
                    }
                }
                return render(request, 'client/gcash_payment.html', context)
        
        except (ValueError, TypeError) as e:
            context = {
                'view': 'payments',
                'client': client,
                'error': str(e),
                'pending_amount': client.balance,
                'plan_fee': plan_fee,
                'month_prices': {
                    1: plan_fee * 1,
                    2: plan_fee * 2,
                    3: plan_fee * 3,
                    6: plan_fee * 6,
                    12: plan_fee * 12,
                }
            }
            return render(request, 'client/gcash_payment.html', context)
    
    context = {
        'view': 'payments',
        'client': client,
        'pending_amount': client.balance,
        'plan_fee': plan_fee,
        'month_prices': {
            1: plan_fee * 1,
            2: plan_fee * 2,
            3: plan_fee * 3,
            6: plan_fee * 6,
            12: plan_fee * 12,
        }
    }
    
    return render(request, 'client/gcash_payment.html', context)


@never_cache
@login_required
def stripe_payment(request):
    """Show Stripe payment form and create a Stripe checkout session."""
    client = _ensure_client_for_user(request.user)
    if not client:
        return render(request, 'client/stripe_payment.html', {
            'view': 'payments',
            'client': None,
            'payments': Payment.objects.none(),
            'total_paid': 0,
            'pending_amount': 0,
            'urgent_count': 0,
            'error': 'Client profile not found yet. Please contact support to activate online payments.',
        })

    plan_fee = float(client.fee)

    if request.method == 'POST':
        payment_type = request.POST.get('payment_type', 'current')
        amount = float(request.POST.get('amount', 0))
        months = int(request.POST.get('months', 1)) if request.POST.get('months') else 1

        try:
            if amount <= 0:
                raise ValueError("Invalid payment amount")

            if payment_type == 'current':
                description = f"Current month payment - {client.name} ({client.plan})"
            elif payment_type == 'advance':
                description = f"Advance payment for {months} month(s) - {client.name} ({client.plan})"
            else:
                raise ValueError("Invalid payment type")

            success_url = request.build_absolute_uri(reverse('dashboard:stripe-success'))
            cancel_url = request.build_absolute_uri(reverse('dashboard:client-payments'))
            payment_response = StripeService.create_checkout_session(
                client=client,
                amount=amount,
                payment_type=payment_type,
                months=months,
                description=description,
                success_url=success_url,
                cancel_url=cancel_url,
            )

            if payment_response['success']:
                return redirect(payment_response['payment_url'])

            error_msg = payment_response.get('error', 'Stripe payment creation failed')
            context = {
                'view': 'payments',
                'client': client,
                'error': error_msg,
                'pending_amount': client.balance,
                'plan_fee': plan_fee,
                'month_prices': {
                    1: plan_fee * 1,
                    2: plan_fee * 2,
                    3: plan_fee * 3,
                    6: plan_fee * 6,
                    12: plan_fee * 12,
                }
            }
            return render(request, 'client/stripe_payment.html', context)

        except (ValueError, TypeError) as e:
            context = {
                'view': 'payments',
                'client': client,
                'error': str(e),
                'pending_amount': client.balance,
                'plan_fee': plan_fee,
                'month_prices': {
                    1: plan_fee * 1,
                    2: plan_fee * 2,
                    3: plan_fee * 3,
                    6: plan_fee * 6,
                    12: plan_fee * 12,
                }
            }
            return render(request, 'client/stripe_payment.html', context)

    context = {
        'view': 'payments',
        'client': client,
        'pending_amount': client.balance,
        'plan_fee': plan_fee,
        'month_prices': {
            1: plan_fee * 1,
            2: plan_fee * 2,
            3: plan_fee * 3,
            6: plan_fee * 6,
            12: plan_fee * 12,
        }
    }

    return render(request, 'client/stripe_payment.html', context)


@login_required
def stripe_success(request):
    """Show Stripe success page after checkout."""
    client = _ensure_client_for_user(request.user)
    return render(request, 'client/stripe_callback.html', {
        'view': 'payments',
        'client': client,
        'success': True,
        'message': 'Payment complete. We will email you a receipt once the transaction is verified.',
        'pending_amount': client.balance if client else 0,
    })


@csrf_exempt
@require_http_methods(["POST"])
def stripe_webhook(request):
    """Stripe webhook endpoint for processing completed payments."""
    try:
        sig_header = request.META.get('HTTP_STRIPE_SIGNATURE', '')
        result = StripeService.process_webhook(request.body, sig_header)
        return JsonResponse(result)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def gcash_callback(request):
    """Handle GCash payment callback"""
    ref_id = request.GET.get('reference_id')
    status = request.GET.get('status')
    
    client = _ensure_client_for_user(request.user)
    if not client:
        return redirect('dashboard:client-dashboard')
    
    if ref_id and status:
        # Verify payment with GCash
        payment_info = GCashService.verify_payment(ref_id)
        
        if payment_info['success'] and payment_info['status'] == 'completed':
            message = 'Payment successful! Your payment has been recorded.'
            success = True

            payment_amount = request.session.get('gcash_amount')
            payment_id = request.session.get('gcash_ref_id') or ref_id

            if request.GET.get('updated') != '1':
                payment_type = request.session.get('gcash_payment_type')
                gcash_months = request.session.get('gcash_months')
                months_param = request.GET.get('months')
                if months_param and months_param.isdigit():
                    try:
                        months_covered = int(months_param)
                    except Exception:
                        months_covered = 0
                elif payment_amount and payment_type in ['current', 'advance']:
                    try:
                        monthly_fee = Decimal(str(client.fee))
                        amount_decimal = Decimal(str(payment_amount))
                        if payment_type == 'advance' and gcash_months:
                            months_covered = int(gcash_months)
                        else:
                            months_covered = int(amount_decimal // monthly_fee) if monthly_fee > 0 else 0
                    except Exception:
                        months_covered = 0
                else:
                    # Fallback: infer months from the most recent verified payment amount today
                    months_covered = 0
                    try:
                        monthly_fee = Decimal(str(client.fee))
                        recent_payment = Payment.objects.filter(client=client.name, status='Verified', date=date.today()).order_by('-created_at').first()
                        if recent_payment and monthly_fee > 0:
                            amount_decimal = Decimal(str(recent_payment.amount))
                            months_covered = int(amount_decimal // monthly_fee)
                            payment_amount = payment_amount or recent_payment.amount
                            payment_id = payment_id or recent_payment.payment_id
                    except Exception:
                        months_covered = 0

                if months_covered >= 1:
                    client = _apply_payment_coverage(client, payment_amount, months_override=months_covered)
            else:
                if payment_amount is None:
                    try:
                        recent_payment = Payment.objects.filter(client=client.name, status='Verified', date=date.today()).order_by('-created_at').first()
                        if recent_payment:
                            payment_amount = recent_payment.amount
                            payment_id = payment_id or recent_payment.payment_id
                    except Exception:
                        payment_amount = Decimal('0.00')

            NotificationService.send_payment_receipt(
                client_id=client.client_id,
                client_name=client.name,
                recipient_email=client.email,
                amount_paid=payment_amount or Decimal('0.00'),
                payment_id=payment_id or ref_id,
                payment_method='GCash',
                payment_date=date.today(),
                new_balance=client.balance,
                plan=client.plan
            )

            request.session.pop('gcash_ref_id', None)
            request.session.pop('gcash_amount', None)
            request.session.pop('gcash_payment_type', None)
            request.session.pop('gcash_months', None)
        else:
            message = 'Payment verification failed or payment is pending.'
            success = False
    else:
        message = 'Payment cancelled.'
        success = False
    
    context = {
        'view': 'payments',
        'client': client,
        'success': success,
        'message': message,
        'pending_amount': client.balance,
    }
    
    return render(request, 'client/gcash_callback.html', context)


@csrf_exempt
@require_http_methods(["POST"])
def gcash_webhook(request):
    """
    Webhook endpoint for GCash payment notifications
    This is called by GCash server when payment is completed
    """
    try:
        webhook_data = json.loads(request.body)
        
        # Verify webhook signature (in production)
        # signature = request.META.get('HTTP_X_GCASH_SIGNATURE')
        # if not GCashService.verify_webhook_signature(signature, request.body):
        #     return JsonResponse({'success': False, 'error': 'Invalid signature'})
        
        # Process the payment
        result = GCashService.process_webhook_payment(webhook_data)
        
        return JsonResponse(result)
    
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_http_methods(["GET"])
def begin_mobile_passkey_enrollment(request):
    """Return WebAuthn options for enrolling a phone biometric passkey."""
    existing = _get_mobile_passkey(request.user)
    exclude_credentials = []
    if existing:
        try:
            existing_data = json.loads(existing.template_data)
            exclude_credentials.append({
                'type': 'public-key',
                'id': existing_data.get('credential_id', ''),
            })
        except json.JSONDecodeError:
            pass

    rp_id, origin = _browser_webauthn_context(request, 'mobile_passkey')
    challenge = b64url_encode(secrets.token_bytes(32))
    request.session['mobile_passkey_enroll_challenge'] = challenge
    request.session.modified = True

    options = {
        'challenge': challenge,
        'rp': {
            'name': 'NetConnect ISP',
            'id': rp_id,
        },
        'user': {
            'id': b64url_encode(str(request.user.id).encode('utf-8')),
            'name': request.user.username,
            'displayName': request.user.get_full_name() or request.user.username,
        },
        'pubKeyCredParams': [
            {'type': 'public-key', 'alg': -7},
        ],
        'timeout': 60000,
        'attestation': 'none',
        'authenticatorSelection': {
            'residentKey': 'preferred',
            'userVerification': 'required',
        },
        'excludeCredentials': exclude_credentials,
    }
    return JsonResponse({'success': True, 'options': options})


@login_required
@require_http_methods(["POST"])
def complete_mobile_passkey_enrollment(request):
    """Store the enrolled phone biometric passkey."""
    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON payload.'}, status=400)

    expected_challenge = request.session.get('mobile_passkey_enroll_challenge', '')
    if not expected_challenge:
        return JsonResponse({'success': False, 'error': 'Enrollment session expired. Start again.'}, status=400)

    credential = payload.get('credential', {})
    response_data = credential.get('response', {})
    client_data_json = b64url_decode(response_data.get('clientDataJSON', ''))
    attestation_object = b64url_decode(response_data.get('attestationObject', ''))

    client_data, challenge, origin = parse_client_data(client_data_json)
    if client_data.get('type') != 'webauthn.create' or challenge != expected_challenge:
        return JsonResponse({'success': False, 'error': 'Enrollment challenge mismatch.'}, status=400)
    expected_origin = request.session.get('mobile_passkey_origin') or origin
    if origin != expected_origin:
        return JsonResponse({'success': False, 'error': 'Enrollment origin mismatch.'}, status=400)

    attestation = decode_cbor(attestation_object)
    auth_data = parse_authenticator_data(attestation.get('authData', b''))
    credential_data = auth_data.get('attested_credential_data')
    if not credential_data:
        return JsonResponse({'success': False, 'error': 'Passkey credential data was not returned.'}, status=400)

    public_key = cose_key_to_public_key(credential_data['cose_public_key'])
    public_numbers = public_key.public_numbers()
    public_key_payload = {
        'kty': 2,
        'alg': -7,
        'crv': 1,
        'x': b64url_encode(public_numbers.x.to_bytes(32, 'big')),
        'y': b64url_encode(public_numbers.y.to_bytes(32, 'big')),
    }
    credential_id = credential_data['credential_id']
    template_payload = {
        'credential_id': b64url_encode(credential_id),
        'public_key': public_key_payload,
        'sign_count': auth_data['sign_count'],
        'rp_id': request.session.get('mobile_passkey_rp_id') or _mobile_passkey_rp_id(request),
        'origin': expected_origin,
        'created_at': timezone.now().isoformat(),
    }

    biometric_data, _ = BiometricData.objects.update_or_create(
        user=request.user,
        biometric_type='mobile_passkey',
        defaults={
            'template_data': json.dumps(template_payload),
            'template_hash': hashlib.sha256(credential_id).hexdigest(),
            'enrolled_from_ip': request.META.get('REMOTE_ADDR', ''),
            'enrollment_device': request.META.get('HTTP_USER_AGENT', '')[:255],
            'enrollment_quality_score': 1.0,
            'enrollment_confidence': 1.0,
            'is_active': True,
        }
    )

    security_profile, _ = UserSecurityProfile.objects.get_or_create(user=request.user)
    security_profile.save()

    request.session.pop('mobile_passkey_enroll_challenge', None)
    request.session['biometric_success_prompt'] = {'kind': 'fingerprint'}
    request.session.modified = True
    messages.success(request, 'Phone fingerprint scanner linked successfully.')
    AuditLogger.log_action(
        user=request.user,
        action_type='security_event',
        description='Enrolled phone biometric passkey',
        ip_address=request.META.get('REMOTE_ADDR', ''),
        user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
        status='success'
    )
    return JsonResponse({'success': True, 'message': 'Phone fingerprint scanner linked successfully.', 'kind': 'fingerprint'})


@login_required
@require_http_methods(["GET"])
def begin_mobile_passkey_assertion(request):
    """Return WebAuthn options for approving an action with the phone fingerprint scanner."""
    credential = _get_mobile_passkey(request.user)
    if not credential:
        return JsonResponse({'success': False, 'error': 'No phone fingerprint scanner is connected yet.'}, status=400)

    try:
        credential_data = json.loads(credential.template_data)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Stored phone biometric data is invalid.'}, status=400)

    challenge = b64url_encode(secrets.token_bytes(32))
    rp_id, _ = _browser_webauthn_context(request, 'mobile_passkey')
    request.session['mobile_passkey_assert_challenge'] = challenge
    request.session.modified = True

    options = {
        'challenge': challenge,
        'rpId': rp_id or credential_data.get('rp_id', _mobile_passkey_rp_id(request)),
        'timeout': 60000,
        'userVerification': 'required',
        'allowCredentials': [
            {
                'type': 'public-key',
                'id': credential_data.get('credential_id', ''),
            }
        ],
    }
    return JsonResponse({'success': True, 'options': options})


@login_required
@require_http_methods(["POST"])
def complete_mobile_passkey_assertion(request):
    """Verify a phone fingerprint scanner assertion."""
    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON payload.'}, status=400)

    expected_challenge = request.session.get('mobile_passkey_assert_challenge', '')
    credential = _get_mobile_passkey(request.user)
    if not credential:
        return JsonResponse({'success': False, 'error': 'No phone fingerprint scanner is connected yet.'}, status=400)

    try:
        credential_data = json.loads(credential.template_data)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Stored phone biometric data is invalid.'}, status=400)

    response_data = payload.get('credential', {}).get('response', {})
    client_data_json = b64url_decode(response_data.get('clientDataJSON', ''))
    authenticator_data_bytes = b64url_decode(response_data.get('authenticatorData', ''))
    signature = b64url_decode(response_data.get('signature', ''))
    credential_id = b64url_decode(payload.get('credential', {}).get('id', ''))

    client_data, challenge, origin = parse_client_data(client_data_json)
    if client_data.get('type') != 'webauthn.get' or challenge != expected_challenge:
        return JsonResponse({'success': False, 'error': 'Approval challenge mismatch.'}, status=400)
    expected_origin = request.session.get('mobile_passkey_origin') or _mobile_passkey_origin(request)
    if origin != expected_origin:
        return JsonResponse({'success': False, 'error': 'Approval origin mismatch.'}, status=400)

    stored_credential_id = b64url_decode(credential_data.get('credential_id', ''))
    if credential_id != stored_credential_id:
        return JsonResponse({'success': False, 'error': 'Passkey credential mismatch.'}, status=400)

    auth_data = parse_authenticator_data(authenticator_data_bytes)
    expected_rp_id = request.session.get('mobile_passkey_rp_id') or _mobile_passkey_rp_id(request)
    expected_rp_hash = hashlib.sha256(expected_rp_id.encode('utf-8')).digest()
    if auth_data['rp_id_hash'] != expected_rp_hash:
        return JsonResponse({'success': False, 'error': 'Passkey RP ID mismatch.'}, status=400)
    if not (auth_data['flags'] & 0x01):
        return JsonResponse({'success': False, 'error': 'Phone biometric must confirm user presence.'}, status=400)
    if not (auth_data['flags'] & 0x04):
        return JsonResponse({'success': False, 'error': 'Phone biometric verification is required.'}, status=400)

    public_key_info = credential_data.get('public_key', {})
    public_key = cose_key_to_public_key({
        1: 2,
        3: -7,
        -1: 1,
        -2: b64url_decode(public_key_info.get('x', '')),
        -3: b64url_decode(public_key_info.get('y', '')),
    })
    try:
        verify_webauthn_assertion(public_key, authenticator_data_bytes, client_data_json, signature)
    except Exception:
        return JsonResponse({'success': False, 'error': 'Phone biometric signature could not be verified.'}, status=400)

    if auth_data['sign_count'] > credential_data.get('sign_count', 0):
        credential_data['sign_count'] = auth_data['sign_count']
        credential.template_data = json.dumps(credential_data)
        credential.last_verified_at = timezone.now()
        credential.save()

    request.session.pop('mobile_passkey_assert_challenge', None)
    request.session['mobile_passkey_verified'] = True
    request.session.modified = True
    AuditLogger.log_action(
        user=request.user,
        action_type='security_event',
        description='Verified phone biometric approval',
        ip_address=request.META.get('REMOTE_ADDR', ''),
        user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
        status='success'
    )
    return JsonResponse({'success': True, 'message': 'Phone fingerprint scanner approved successfully.'})


    device_info = (request.META.get('HTTP_USER_AGENT', '') or 'bridge')[:500]
    fingerprint_position = str(payload.get('fingerprint_position', 'unknown')).strip() or 'unknown'

    if action in ('enroll_phone_biometric', 'approve_face_biometric'):
        face_template = _coerce_fingerprint_payload(payload.get('face_template') or payload.get('face_sample'))
        if not face_template:
            return JsonResponse({'success': False, 'error': 'Missing face biometric template from the bridge.'}, status=400)

        biometric_data, _ = BiometricData.objects.update_or_create(
            user=user,
            biometric_type='mobile_passkey',
            defaults={
                'template_data': json.dumps({
                    'credential_id': f'bridge-{user.id}-{uuid.uuid4().hex[:12]}',
                    'public_key': {'x': 'phone-biometric', 'y': 'face-enrollment'},
                    'sign_count': 1,
                    'rp_id': _mobile_passkey_rp_id(request),
                    'origin': _mobile_passkey_origin(request),
                    'source': 'phone_biometric_bridge',
                    'biometric_kind': 'face',
                    'mode': 'enroll' if action == 'enroll_phone_biometric' else 'approve',
                    'face_template': face_template,
                }),
                'template_hash': hashlib.sha256(str(face_template).encode('utf-8')).hexdigest(),
                'enrolled_from_ip': ip_address,
                'enrollment_device': device_info,
                'enrollment_quality_score': 1.0,
                'enrollment_confidence': 1.0,
                'is_active': True,
            }
        )
        request.session['mobile_passkey_verified'] = True
        request.session['mobile_passkey_enrolled'] = True
        request.session['biometric_success_prompt'] = {'kind': 'face'}
        request.session.modified = True
        login(request, user)
        message = 'Phone biometric enrollment completed.' if action == 'enroll_phone_biometric' else 'Phone biometric face approval completed.'
        return JsonResponse({'success': True, 'message': message, 'kind': 'face'})

    if action in ('save_fingerprint', 'replace_fingerprint'):
        bridge_template = _coerce_fingerprint_payload(
            payload.get('fingerprint_template') or payload.get('fingerprint_sample')
        )
        if not bridge_template:
            return JsonResponse({'success': False, 'error': 'Missing fingerprint template from the bridge.'}, status=400)

        verification_template = _coerce_fingerprint_payload(
            payload.get('verification_template') or payload.get('fingerprint_verify_sample')
        )

        if fingerprint_data and not verification_template:
            return JsonResponse({'success': False, 'error': 'Please verify the current fingerprint before replacing it.'}, status=400)

        if fingerprint_data and verification_template:
            verify_result = FingerprintAuthService.verify_fingerprint(
                user,
                verification_template,
                ip_address=ip_address,
                device_info=device_info,
                reason='bridge_replace'
            )
            if not verify_result['success']:
                return JsonResponse({'success': False, 'error': verify_result['error']}, status=400)

        enroll_result = FingerprintAuthService.enroll_fingerprint(
            user,
            bridge_template,
            fingerprint_position=fingerprint_position,
            ip_address=ip_address,
            device_info=device_info
        )
        status_code = 200 if enroll_result['success'] else 400
        return JsonResponse(enroll_result, status=status_code)

    if action == 'delete_fingerprint':
        verification_template = _coerce_fingerprint_payload(
            payload.get('verification_template') or payload.get('fingerprint_verify_sample')
        )
        if fingerprint_data and not verification_template:
            return JsonResponse({'success': False, 'error': 'Please verify the current fingerprint before deleting it.'}, status=400)

        if fingerprint_data and verification_template:
            verify_result = FingerprintAuthService.verify_fingerprint(
                user,
                verification_template,
                ip_address=ip_address,
                device_info=device_info,
                reason='bridge_delete'
            )
            if not verify_result['success']:
                return JsonResponse({'success': False, 'error': verify_result['error']}, status=400)

        if FingerprintAuthService.remove_fingerprint(user):
            return JsonResponse({'success': True, 'message': 'Fingerprint profile removed.'})
        return JsonResponse({'success': False, 'error': 'Unable to remove fingerprint profile.'}, status=400)

    if action == 'verify_fingerprint':
        verification_template = _coerce_fingerprint_payload(
            payload.get('verification_template') or payload.get('fingerprint_template')
        )
        if not verification_template:
            return JsonResponse({'success': False, 'error': 'Missing fingerprint template for verification.'}, status=400)
        verify_result = FingerprintAuthService.verify_fingerprint(
            user,
            verification_template,
            ip_address=ip_address,
            device_info=device_info,
            reason='bridge_verify'
        )
        status_code = 200 if verify_result['success'] else 400
        return JsonResponse(verify_result, status=status_code)

    return JsonResponse({'success': False, 'error': 'Unsupported bridge action.'}, status=400)


@login_required
def test_gcash_payment(request):
    """
    Test payment page for mock mode
    Simulates the GCash payment process for testing
    """
    reference_id = request.GET.get('reference_id', '')
    amount = request.GET.get('amount', '0')
    
    if request.method == 'POST':
        payment_amount = request.POST.get('amount', amount)
        # Simulate payment based on status selection
        payment_status = request.POST.get('payment_status', 'success')
        
        if payment_status == 'success':
            # Create payment record directly (simulating webhook)
            try:
                client = _ensure_client_for_user(request.user)
                if not client:
                    raise Client.DoesNotExist
                
                # Generate a unique payment ID
                payment_id = _generate_payment_id()
                
                # Create payment record
                payment = Payment.objects.create(
                    payment_id=payment_id,
                    client=client.name,
                    date=date.today(),
                    amount=Decimal(payment_amount),
                    period='Current Month',
                    method='GCash',
                    status='Verified'
                )
                
                # Update client balance and extend coverage immediately for mock payments
                client = _apply_payment_coverage(client, payment_amount)

                # Store payment metadata so callback can log a receipt when the mock payment flow completes.
                request.session['gcash_ref_id'] = reference_id
                request.session['gcash_amount'] = payment_amount
                request.session['gcash_payment_type'] = 'current'
                request.session['gcash_months'] = 1
                request.session.modified = True

                # Redirect to success callback page; due date already updated in mock mode
                return redirect(f'/client/gcash-callback/?reference_id={reference_id}&status=success&updated=1')
            except Client.DoesNotExist:
                error = "Client not found"
                context = {
                    'reference_id': reference_id,
                    'amount': amount,
                    'error': error
                }
                return render(request, 'client/test_payment.html', context)
            except Exception as e:
                error = f"Payment processing error: {str(e)}"
                context = {
                    'reference_id': reference_id,
                    'amount': amount,
                    'error': error
                }
                return render(request, 'client/test_payment.html', context)
        else:
            # For failed or cancelled, redirect to callback with appropriate status
            status_map = {
                'failed': 'failed',
                'cancelled': 'cancelled'
            }
            status = status_map.get(payment_status, 'cancelled')
            return redirect(f'/client/gcash-callback/?reference_id={reference_id}&status={status}')
    
    context = {
        'reference_id': reference_id,
        'amount': amount,
    }
    
    return render(request, 'client/test_payment.html', context)


@login_required
def test_overdue_notification(request):
    """
    Test page for simulating overdue payment notifications
    Allows testing email and SMS notification sending
    """
    client = _ensure_client_for_user(request.user)
    if not client:
        return render(request, 'client/test_overdue.html', {
            'error': 'Client not found for this account',
            'urgent_count': 0,
        })
    
    # Get urgent notification count for badge
    urgent_count = 0
    urgent_sms = OverdueNotification.objects.filter(
        client=client.client_id,
        notification_type__in=['Second Notice', 'Disconnection Warning']
    ).count()
    urgent_email = OverdueNotification.objects.filter(
        client=client.client_id,
        notification_type__in=['Second Notice', 'Disconnection Warning']
    ).count()
    urgent_count = urgent_sms + urgent_email
    
    if request.method == 'POST':
        from api.notification_service import NotificationService
        from django.utils import timezone
        from api.models import OverdueNotification
        
        try:
            # Get form data
            days_overdue = int(request.POST.get('days_overdue', 1))
            
            # Send test notifications
            result = NotificationService.send_overdue_notification(
                client_id=client.client_id,
                client_name=client.name,
                phone_number=client.phone,
                email=client.email,
                plan=client.plan,
                amount_due=client.balance,
                due_date=client.due_date,
                days_overdue=days_overdue
            )
            
            notification = NotificationService.ensure_overdue_notification(
                client,
                days_overdue=days_overdue,
                force=True,
            )
            
            context = {
                'client': client,
                'success': True,
                'notification_id': notification.notification_id if notification else None,
                'result': result,
                'days_overdue': days_overdue,
                'urgent_count': urgent_count,
            }
            return render(request, 'client/test_overdue_result.html', context)
        
        except Exception as e:
            context = {
                'client': client,
                'error': f'Error sending notifications: {str(e)}',
                'days_overdue_value': request.POST.get('days_overdue', 1),
                'urgent_count': urgent_count,
            }
            return render(request, 'client/test_overdue.html', context)
    
    # GET request - show test form
    context = {
        'client': client,
        'grace_period_days': 3,
        'urgent_count': urgent_count,
    }
    return render(request, 'client/test_overdue.html', context)


@never_cache
@login_required
def client_notifications(request):
    """
    View for clients to see their own notifications
    """
    client = _ensure_client_for_user(request.user)
    if not client:
        return render(request, 'client/notifications.html', {'error': 'Client profile not found'})
    
    # Calculate days overdue
    days_overdue = 0
    if client.due_date:
        days_overdue = (timezone.now().date() - client.due_date).days

    if days_overdue > 0:
        NotificationService.ensure_overdue_notification(client, days_overdue=days_overdue)

    # Get overdue notification records created by the billing workflow
    overdue_notifications = OverdueNotification.objects.filter(
        client=client.client_id,
        hide_from_notifications=False
    ).order_by('-sent_at')

    sms_notifications = overdue_notifications.filter(sms_sent=True)
    email_notifications = overdue_notifications.filter(email_sent=True)

    # Helper to map notification types to categories (matching admin)
    def _notification_category(notification_type):
        if notification_type in ('Overdue Notice', 'First Notice', 'Second Notice'):
            return 'Payment Overdue Alert'
        if notification_type == 'Disconnection Warning':
            return 'Disconnection'
        return 'General Notification'

    # Combine and sort all notifications by date using admin-shaped objects
    all_notifications = []
    for n in overdue_notifications:
        all_notifications.append({
            'id': n.notification_id,
            'type': 'overdue',
            'notification_type': n.notification_type,
            'category': _notification_category(n.notification_type),
            'title': n.notification_type,
            'client_name': client.name,
            'channel': 'Overdue',
            'description': n.email_response or n.sms_response or f"Billing notice: {n.notification_type}",
            'amount_due': n.amount_due,
            'ticket_id': None,
            'sent_at': n.sent_at or n.created_at,
            'is_new': False,
            'status': 'New',
        })

    ticket_activities = ActivityLog.objects.filter(
        entity_type='Ticket',
        entity_name=client.name,
        activity_type__in=[
            'ticket_created',
            'ticket_scheduled',
            'ticket_updated',
            'ticket_resolved',
            'ticket_closed',
            'ticket_reschedule_requested',
        ],
    ).order_by('-created_at')

    for activity in ticket_activities:
        event_type = activity.activity_type.replace('_', ' ').title()
        all_notifications.append({
            'id': activity.entity_id if activity.entity_type == 'Ticket' else f'activity-{activity.activity_id}',
            'type': 'ticket',
            'notification_type': event_type,
            'category': 'Support Tickets',
            'title': event_type,
            'client_name': client.name,
            'channel': 'Ticket',
            'description': activity.description,
            'amount_due': None,
            'ticket_id': activity.entity_id if activity.entity_type == 'Ticket' else None,
            'sent_at': activity.created_at,
            'is_new': activity.is_new,
            'status': 'Read' if not activity.is_new else 'New',
        })

    if days_overdue > 0:
        current_notice_type = NotificationService.get_notification_type(days_overdue)
        has_matching_notice = any(
            item.get('title') == current_notice_type for item in all_notifications
        )
        if not has_matching_notice:
            portal_id = f'portal-{client.client_id}-{days_overdue}'
            # Respect previously hidden portal notifications stored in session
            hidden_portals = request.session.get('hidden_portal_notices', []) or []
            if portal_id in hidden_portals:
                pass
            else:
                all_notifications.append({
                'id': f'portal-{client.client_id}-{days_overdue}',
                'type': 'overdue',
                'notification_type': current_notice_type,
                'category': _notification_category(current_notice_type),
                'title': current_notice_type,
                'client_name': client.name,
                'channel': 'Overdue',
                'description': (
                    f"Your account is {('overdue' if days_overdue <= 3 else 'past due')} and requires payment to keep service active."
                ),
                'amount_due': client.balance,
                'ticket_id': None,
                'sent_at': timezone.now(),
                'is_new': True,
                'status': 'New',
            })

    all_notifications.sort(key=lambda x: x['sent_at'], reverse=True)
    
    # Get client status
    is_overdue = client.status == 'Overdue'
    is_disconnected = client.status == 'Disconnected'
    is_under_maintenance = getattr(client, 'under_maintenance', False)  # Check if client has maintenance status
    
    # Count urgent notifications (red - Second Notice & Disconnection Warning)
    urgent_notifications = [n for n in all_notifications if n['notification_type'] in ['Second Notice', 'Disconnection Warning']]
    warning_notifications = [n for n in all_notifications if n['notification_type'] == 'First Notice']
    
    # Count by notification type
    type_counts = {}
    for notif in all_notifications:
        notif_type = notif['notification_type']
        type_counts[notif_type] = type_counts.get(notif_type, 0) + 1
    
    # Add count to each notification
    notifications_with_counts = []
    for notif in all_notifications[:10]:
        notif['type_count'] = type_counts.get(notif['notification_type'], 0)
        notifications_with_counts.append(notif)

    active_notifications = [n for n in all_notifications if n.get('status', 'New') == 'New']
    archived_notifications = [n for n in all_notifications if n.get('status', 'New') != 'New']
    categories = ['All'] + sorted({n.get('notification_type', 'General') for n in all_notifications})
    search_query = request.GET.get('q', '').strip()
    category_filter = request.GET.get('category', '').strip()
    active_count = len(active_notifications)
    archived_count = len(archived_notifications)

    context = {
        'client': client,
        'sms_notifications': sms_notifications,
        'email_notifications': email_notifications,
        'all_notifications': notifications_with_counts,  # Show last 10
        'active_notifications': active_notifications,
        'archived_notifications': archived_notifications,
        'categories': categories,
        'search_query': search_query,
        'category_filter': category_filter,
        'active_count': active_count,
        'archived_count': archived_count,
        'is_overdue': is_overdue,
        'is_disconnected': is_disconnected,
        'is_under_maintenance': is_under_maintenance,
        'days_overdue': max(0, days_overdue),
        'total_sms': sms_notifications.count() if hasattr(sms_notifications, 'count') else len(sms_notifications),
        'total_email': email_notifications.count() if hasattr(email_notifications, 'count') else len(email_notifications),
        # header urgent_count should reflect total New notifications shown in the UI
        'urgent_count': active_count,
        'warning_count': len(warning_notifications),
        'total_notifications': len(all_notifications),
        'view': 'notifications',
    }
    context.update(_security_context(request, request.user))
    
    return render(request, 'client/notifications.html', context)


@csrf_exempt
@login_required
@require_http_methods(['POST'])
def client_mark_notification_read(request):
    """Allow a logged-in client to mark their own notification as read."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid request'}, status=400)

    import json
    client = _ensure_client_for_user(request.user)
    if not client:
        return JsonResponse({'success': False, 'message': 'Client profile not found'}, status=404)

    try:
        data = json.loads(request.body)
        notification_id = data.get('notification_id')
        notification_type = data.get('notification_type')

        if notification_type == 'overdue':
            # If this is a portal-generated id, persist hide in session so it stays hidden across refresh
            if isinstance(notification_id, str) and notification_id.startswith('portal-'):
                hidden = request.session.get('hidden_portal_notices', [])
                if notification_id not in hidden:
                    hidden.append(notification_id)
                    request.session['hidden_portal_notices'] = hidden
                    request.session.modified = True
            else:
                # Archive the persisted OverdueNotification record
                OverdueNotification.objects.filter(notification_id=notification_id, client=client.client_id).update(hide_from_notifications=True)
        elif notification_type in ('ticket_activity', 'ticket'):
            # Support both activity record references (activity-<id>) and ticket IDs (e.g. TKT...)
            nid = str(notification_id)
            if nid.startswith('activity-'):
                act_str = nid.replace('activity-', '')
                try:
                    act_id = int(act_str)
                    ActivityLog.objects.filter(activity_id=act_id, entity_type='Ticket', entity_name=client.name).update(is_new=False)
                except ValueError:
                    # malformed activity id, ignore
                    pass
            else:
                # Treat as a ticket identifier stored in ActivityLog.entity_id
                ActivityLog.objects.filter(entity_type='Ticket', entity_id=nid, entity_name=client.name).update(is_new=False)
        else:
            # For state or unknown client-only notifications, no persistent update is available.
            pass

        return JsonResponse({'success': True})
    except Exception as e:
        # Log debug information to a file for diagnosis
        try:
            with open('tmp_mark_read_debug.log', 'a', encoding='utf-8') as fh:
                fh.write(f"--- {datetime.now().isoformat()} ---\n")
                fh.write('Request body:\n')
                try:
                    fh.write(request.body.decode('utf-8') + '\n')
                except Exception:
                    fh.write(str(request.body) + '\n')
                fh.write('Exception:\n')
                fh.write(traceback.format_exc())
                fh.write('\n')
        except Exception:
            pass
        return JsonResponse({'success': False, 'message': str(e)}, status=400)


@csrf_exempt
@login_required
@require_http_methods(['POST'])
def client_delete_notification(request):
    """Allow a logged-in client to hide their own archived notification."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid request'}, status=400)

    import json
    client = _ensure_client_for_user(request.user)
    if not client:
        return JsonResponse({'success': False, 'message': 'Client profile not found'}, status=404)

    try:
        data = json.loads(request.body)
        notification_id = data.get('notification_id')
        notification_type = data.get('notification_type')

        if notification_type == 'overdue':
            if isinstance(notification_id, str) and notification_id.startswith('portal-'):
                hidden = request.session.get('hidden_portal_notices', [])
                if notification_id not in hidden:
                    hidden.append(notification_id)
                    request.session['hidden_portal_notices'] = hidden
                    request.session.modified = True
            else:
                OverdueNotification.objects.filter(notification_id=notification_id, client=client.client_id).update(hide_from_notifications=True)
        elif notification_type in ('ticket_activity', 'ticket'):
            nid = str(notification_id)
            if nid.startswith('activity-'):
                act_str = nid.replace('activity-', '')
                try:
                    act_id = int(act_str)
                    ActivityLog.objects.filter(activity_id=act_id, entity_type='Ticket', entity_name=client.name).update(is_new=False)
                except ValueError:
                    pass
            else:
                ActivityLog.objects.filter(entity_type='Ticket', entity_id=nid, entity_name=client.name).update(is_new=False)
        else:
            pass

        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=400)


@login_required
def notification_settings(request):
    """
    Manage notification preferences
    """
    client = _ensure_client_for_user(request.user)
    if not client:
        return render(request, 'client/notification_settings.html', {
            'error': 'Client profile not found',
            'urgent_count': 0,
        })
    
    # Get urgent notification count for badge
    urgent_count = 0
    urgent_sms = OverdueNotification.objects.filter(
        client=client.client_id,
        notification_type__in=['Second Notice', 'Disconnection Warning']
    ).count()
    urgent_email = OverdueNotification.objects.filter(
        client=client.client_id,
        notification_type__in=['Second Notice', 'Disconnection Warning']
    ).count()
    urgent_count = urgent_sms + urgent_email
    
    # Get or create notification settings
    settings, created = NotificationSettings.objects.get_or_create(
        client_id=client.client_id,
        defaults={
            'client_name': client.name,
            'email': client.email,
            'phone': client.phone,
            'notifications_enabled': True,
            'notification_method': 'both',
            'grace_period_days': 3,
            'send_first_notice': True,
            'send_second_notice': True,
            'send_disconnection_warning': True,
            'auto_disconnect_enabled': True,
            'allow_email_reminders': True,
            'allow_sms_reminders': True,
        }
    )
    
    if request.method == 'POST':
        form = NotificationSettingsForm(request.POST)
        if form.is_valid():
            # Update settings from form data
            settings.notifications_enabled = form.cleaned_data['notifications_enabled']
            settings.notification_method = form.cleaned_data['notification_method']
            settings.grace_period_days = form.cleaned_data['grace_period_days']
            settings.send_first_notice = form.cleaned_data['send_first_notice']
            settings.send_second_notice = form.cleaned_data['send_second_notice']
            settings.send_disconnection_warning = form.cleaned_data['send_disconnection_warning']
            settings.auto_disconnect_enabled = form.cleaned_data['auto_disconnect_enabled']
            settings.allow_email_reminders = form.cleaned_data['allow_email_reminders']
            settings.allow_sms_reminders = form.cleaned_data['allow_sms_reminders']
            settings.save()
            
            context = {
                'client': client,
                'settings': settings,
                'form': form,
                'success': True,
                'message': '✓ Your notification settings have been saved successfully!',
                'urgent_count': urgent_count,
            }
            return render(request, 'client/notification_settings.html', context)
    else:
        # Populate form with existing settings
        initial_data = {
            'notifications_enabled': settings.notifications_enabled,
            'notification_method': settings.notification_method,
            'grace_period_days': settings.grace_period_days,
            'send_first_notice': settings.send_first_notice,
            'send_second_notice': settings.send_second_notice,
            'send_disconnection_warning': settings.send_disconnection_warning,
            'auto_disconnect_enabled': settings.auto_disconnect_enabled,
            'allow_email_reminders': settings.allow_email_reminders,
            'allow_sms_reminders': settings.allow_sms_reminders,
        }
        form = NotificationSettingsForm(initial=initial_data)
    
    context = {
        'client': client,
        'settings': settings,
        'form': form,
        'view': 'settings',
        'urgent_count': urgent_count,
    }
    context.update(_security_context(request, request.user))
    return render(request, 'client/notification_settings.html', context)


@never_cache
@login_required
def security_settings_legacy(request):
    """Legacy security settings URL that redirects to the versioned page."""
    return redirect('dashboard:security-settings')


@never_cache
@login_required
def security_settings(request):
    """Manage biometric authentication and security verification settings."""
    client = _ensure_client_for_user(request.user)
    if not client:
        return render(request, 'client/security_settings.html', {
            'error': 'Client profile not found yet.',
            'urgent_count': 0,
        })

    security_profile, _ = UserSecurityProfile.objects.get_or_create(user=request.user)
    mfa_settings, _ = MFASettings.objects.get_or_create(user=request.user)
    facial_data = BiometricData.objects.filter(
        user=request.user,
        biometric_type='facial',
        is_active=True
    ).first()
    mobile_passkey_data = BiometricData.objects.filter(
        user=request.user,
        biometric_type='mobile_passkey',
        is_active=True
    ).first()
    if not facial_data and mobile_passkey_data:
        facial_data = mobile_passkey_data
    fingerprint_data = BiometricData.objects.filter(
        user=request.user,
        biometric_type='fingerprint',
        is_active=True
    ).first()

    # Get notification badge count (uses same logic as notifications view)
    urgent_count = _get_notification_badge_count(client)
    form_state = _pop_security_form_state(request)
    biometric_success_prompt = request.session.pop('biometric_success_prompt', None)

    if request.method == 'POST':
        action = request.POST.get('action', '')
        current_password = request.POST.get('current_password', '')
        otp_code = request.POST.get('otp_code', '').strip()
        fingerprint_position = request.POST.get('fingerprint_position', 'unknown')
        fingerprint_enrollment_mode = str(request.POST.get('fingerprint_enrollment_mode', 'create')).strip().lower()
        face_enrollment_mode = str(request.POST.get('face_enrollment_mode', 'create')).strip().lower()
        phone_biometric_verified = request.session.pop('mobile_passkey_verified', False)
        authenticated_user = authenticate(
            request,
            username=request.user.username,
            password=current_password
        )
        _remember_security_form_state(
            request,
            current_password=current_password,
            otp_code=otp_code,
            mfa_method=request.POST.get('mfa_method', mfa_settings.method),
            fingerprint_position=fingerprint_position,
            fingerprint_template_json=request.POST.get('fingerprint_template_json', ''),
            fingerprint_verify_json=request.POST.get('fingerprint_verify_json', ''),
        )

        if 'send_otp' in request.POST:
            otp_result = OTPService.send_otp(
                request.user,
                ip_address=request.META.get('REMOTE_ADDR', ''),
                user_agent=request.META.get('HTTP_USER_AGENT', '')[:500]
            )
            if otp_result['success']:
                messages.success(request, otp_result['message'] or 'OTP sent to your email. Enter it before saving changes.')
            else:
                messages.error(request, otp_result['error'])
            return redirect('dashboard:security-settings')

        if authenticated_user is None:
            messages.error(request, 'Current password is incorrect.')
            return redirect('dashboard:security-settings')

        if action == 'save_auth_settings':
            enable_mfa = request.POST.get('enable_mfa') == 'on'
            require_every_login = request.POST.get('require_on_every_login') == 'on'
            require_sensitive_actions = request.POST.get('require_biometric_sensitive') == 'on'
            require_suspicious = request.POST.get('require_on_suspicious_login') == 'on'
            allow_otp_login = request.POST.get('allow_otp_login') == 'on'
            selected_method = 'password_otp' if enable_mfa and (allow_otp_login or require_every_login or require_suspicious) else ''

            if enable_mfa:
                mfa_result = MFAService.enable_mfa(request.user, method=selected_method)
                if not mfa_result['success']:
                    messages.error(request, mfa_result['error'])
                    return redirect('dashboard:security-settings')
            else:
                MFAService.disable_mfa(request.user)
                mfa_settings.is_enabled = False

            mfa_settings.method = selected_method
            mfa_settings.require_on_every_login = require_every_login
            mfa_settings.require_on_suspicious_login = require_suspicious
            mfa_settings.require_biometric_for_sensitive_actions = require_sensitive_actions
            mfa_settings.allow_otp_login = allow_otp_login
            mfa_settings.save()

            security_profile.mfa_enabled = enable_mfa
            security_profile.mfa_method = selected_method if enable_mfa else ''
            security_profile.save()

            AuditLogger.log_action(
                user=request.user,
                action_type='security_event',
            description='Updated security and two-step verification settings',
            ip_address=request.META.get('REMOTE_ADDR', ''),
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
            status='success'
        )
            messages.success(request, 'Authentication settings updated successfully.')
            return redirect('dashboard:security-settings')

        if action in ('save_fingerprint', 'replace_fingerprint'):
            sample = _coerce_fingerprint_payload(
                request.POST.get('fingerprint_template_json', '') or request.FILES.get('fingerprint_sample')
            )
            verification_sample = _coerce_fingerprint_payload(
                request.POST.get('fingerprint_verify_json', '') or request.FILES.get('fingerprint_verify_sample')
            )
            skip_fingerprint_verification = fingerprint_enrollment_mode == 'append'

            # If no sample provided, try to use phone biometric
            if not sample:
                mobile_passkey = _get_mobile_passkey(request.user)
                if mobile_passkey:
                    try:
                        mobile_passkey_data = json.loads(mobile_passkey.template_data)
                    except json.JSONDecodeError:
                        mobile_passkey_data = {}
                    sample = {
                        'source': 'mobile_passkey',
                        'credential_id': mobile_passkey_data.get('credential_id', ''),
                        'public_key': mobile_passkey_data.get('public_key', {}),
                        'sign_count': mobile_passkey_data.get('sign_count', 0),
                    }
                    fingerprint_position = 'phone'
                else:
                    messages.error(request, 'No phone biometric found. Please set up phone biometric authentication first in Security Settings.')
                    return redirect('dashboard:security-settings')

            if not sample:
                messages.error(request, 'No fingerprint sample provided.')
                return redirect('dashboard:security-settings')

            if fingerprint_data and verification_sample:
                verify_result = FingerprintAuthService.verify_fingerprint(
                    request.user,
                    verification_sample,
                    ip_address=request.META.get('REMOTE_ADDR', ''),
                    device_info=request.META.get('HTTP_USER_AGENT', '')[:500]
                )
                if not verify_result['success']:
                    messages.error(request, verify_result['error'])
                    return redirect('dashboard:security-settings')
            elif fingerprint_data and not verification_sample and not phone_biometric_verified and not skip_fingerprint_verification:
                messages.error(request, 'Please verify your current fingerprint or approve with your phone before replacing it.')
                return redirect('dashboard:security-settings')

            enroll_result = FingerprintAuthService.enroll_fingerprint(
                request.user,
                sample,
                fingerprint_position=request.POST.get('fingerprint_position', 'unknown'),
                ip_address=request.META.get('REMOTE_ADDR', ''),
                device_info=request.META.get('HTTP_USER_AGENT', '')[:500]
            )
            if enroll_result['success']:
                messages.success(request, 'Fingerprint profile saved successfully.')
                request.session['biometric_success_prompt'] = {'kind': 'fingerprint'}
                request.session.modified = True
            else:
                messages.error(request, enroll_result['error'])
            return redirect('dashboard:security-settings')

        if action == 'delete_fingerprint':
            verification_sample = _coerce_fingerprint_payload(
                request.POST.get('fingerprint_verify_json', '') or request.FILES.get('fingerprint_verify_sample')
            )
            if fingerprint_data and not verification_sample and not phone_biometric_verified:
                messages.error(request, 'Please verify your current fingerprint or approve with your phone before deleting it.')
                return redirect('dashboard:security-settings')

            if fingerprint_data and verification_sample:
                verify_result = FingerprintAuthService.verify_fingerprint(
                    request.user,
                    verification_sample,
                    ip_address=request.META.get('REMOTE_ADDR', ''),
                    device_info=request.META.get('HTTP_USER_AGENT', '')[:500]
                )
                if not verify_result['success']:
                    messages.error(request, verify_result['error'])
                    return redirect('dashboard:security-settings')

            if FingerprintAuthService.remove_fingerprint(request.user):
                messages.success(request, 'Fingerprint profile removed.')
            else:
                messages.error(request, 'Unable to remove fingerprint profile.')
            return redirect('dashboard:security-settings')

        if action in ('save_face', 'replace_face'):
            face_front = _decode_data_url(request.POST.get('face_image_front', ''))

            if not face_front:
                if request.session.get('mobile_passkey_enrolled') or request.session.get('mobile_passkey_verified'):
                    security_profile.facial_data_enrolled = True
                    security_profile.save(update_fields=['facial_data_enrolled', 'updated_at'])
                    messages.success(request, 'Phone face biometric enrollment recorded successfully.')
                    request.session.pop('mobile_passkey_enrolled', None)
                    request.session.pop('mobile_passkey_verified', None)
                    request.session.modified = True
                    return redirect('dashboard:security-settings')
                messages.error(request, 'Please capture your face first.')
                return redirect('dashboard:security-settings')

            if facial_data and face_enrollment_mode != 'append':
                verify_result = FacialRecognitionService.verify_face(
                    request.user,
                    face_front,
                    ip_address=request.META.get('REMOTE_ADDR', ''),
                    device_info=request.META.get('HTTP_USER_AGENT', '')[:500],
                    reason='profile_update'
                )
                if not verify_result['success']:
                    messages.error(request, verify_result['error'])
                    return redirect('dashboard:security-settings')

            enroll_result = FacialRecognitionService.enroll_facial_data(
                request.user,
                face_front,
                ip_address=request.META.get('REMOTE_ADDR', ''),
                device_info=request.META.get('HTTP_USER_AGENT', '')[:500]
            )
            if enroll_result['success']:
                messages.success(request, 'Facial profile saved successfully.')
                request.session['biometric_success_prompt'] = {'kind': 'face'}
                request.session.modified = True
            else:
                messages.error(request, enroll_result['error'])
            return redirect('dashboard:security-settings')

        if action == 'delete_face':
            face_data = _decode_data_url(request.POST.get('face_image_data', ''))
            if facial_data and not face_data:
                messages.error(request, 'Please capture a face image to verify before deleting it.')
                return redirect('dashboard:security-settings')

            if facial_data:
                verify_result = FacialRecognitionService.verify_face(
                    request.user,
                    face_data,
                    ip_address=request.META.get('REMOTE_ADDR', ''),
                    device_info=request.META.get('HTTP_USER_AGENT', '')[:500],
                    reason='profile_delete'
                )
                if not verify_result['success']:
                    messages.error(request, verify_result['error'])
                    return redirect('dashboard:security-settings')

            if FacialRecognitionService.remove_facial_data(request.user):
                messages.success(request, 'Facial profile removed.')
            else:
                messages.error(request, 'Unable to remove facial profile.')
            return redirect('dashboard:security-settings')

        if action == 'delete_all_biometrics':
            if FingerprintAuthService.remove_fingerprint(request.user):
                pass
            if FacialRecognitionService.remove_facial_data(request.user):
                pass
            security_profile.facial_data_enrolled = False
            security_profile.fingerprint_enrolled = False
            security_profile.save()
            messages.success(request, 'All biometric data was removed from your account.')
            AuditLogger.log_action(
                user=request.user,
                action_type='security_event',
                description='Removed all biometric data',
                ip_address=request.META.get('REMOTE_ADDR', ''),
                user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
                status='success'
            )
            return redirect('dashboard:security-settings')

        messages.error(request, 'Unknown action.')
        return redirect('dashboard:security-settings')

    biometric_history = AuditLog.objects.filter(
        user=request.user,
        action_type__in=[
            'otp_request', 'otp_verify',
            'facial_enroll', 'facial_verify',
            'fingerprint_enroll', 'fingerprint_verify',
            'mfa_enable', 'mfa_disable',
            'security_event'
        ]
    ).order_by('-timestamp')[:10]

    last_biometric_update = None
    candidates = [item for item in [facial_data, fingerprint_data, mobile_passkey_data] if item is not None]
    if candidates:
        last_biometric_update = max(item.updated_at for item in candidates)
    else:
        last_biometric_update = security_profile.updated_at

    security_level = _get_security_level(
        request.user,
        security_profile,
        mfa_settings,
        facial_data is not None,
        fingerprint_data is not None
    )

    context = {
        'client': client,
        'view': 'security-settings',
        'urgent_count': urgent_count,
        'biometric_history': biometric_history,
        'supported_mfa_methods': MFASettings.MFA_METHODS,
        'security_form_state': form_state,
        'biometric_success_prompt': biometric_success_prompt,
    }
    context.update(_security_context(request, request.user, security_profile=security_profile))
    return render(request, 'client/security_settings.html', context)


@login_required
def dismiss_biometric_prompt(request):
    """Remember that the user chose to defer biometric enrollment."""
    if request.method == 'POST':
        request.session['biometric_prompt_dismissed'] = True
        messages.info(request, 'Biometric setup reminder will stay hidden for this session.')
    return redirect(request.POST.get('next', 'client-dashboard'))
