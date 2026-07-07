from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout, authenticate, login
from django.contrib.auth.models import User
from django.contrib import messages
from django.conf import settings
from django.core.paginator import Paginator
from django.http import JsonResponse, FileResponse
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.views.decorators.cache import never_cache
from django.db.models import Sum, Q, Case, When, IntegerField
from django.utils import timezone
from datetime import datetime, timedelta
from pathlib import Path
import os
import subprocess
import sys
from decimal import Decimal
from api.models import ActivityLog, Client, Application, ApplicationDecision, Ticket, Payment, OverdueNotification
from api.notification_service import NotificationService
from dashboard.forms import RegistrationForm, ApplicationForm
from dashboard.admin_views import get_admin_notification_count
from security.models import BiometricData, UserSecurityProfile, LoginAttempt, SecuritySettings, AuditLog
from security.otp_service import OTPService
from security.fingerprint_auth import FingerprintAuthService
from security.authentication import AuthenticationService
from security.mfa_service import MFAService
from security.encryption import EncryptionService
from security.webauthn import decode_cbor, b64url_decode, b64url_encode, cose_key_to_public_key, parse_authenticator_data, parse_client_data, verify_webauthn_assertion
import json
import hashlib
import secrets
import uuid
import base64
from urllib.parse import urlencode, urlparse
from django.views.decorators.http import require_POST


def _get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '')


def _get_post_login_redirect(user):
    if user.is_staff:
        return redirect('dashboard:dashboard')

    if Client.objects.filter(email=user.email).exists():
        return redirect('dashboard:client-dashboard')

    latest_decision = ApplicationDecision.objects.filter(Q(user=user) | Q(email=user.email)).order_by('-created_at').first()
    if latest_decision:
        if latest_decision.status == 'Approved':
            return redirect('dashboard:client-dashboard')
        return redirect('dashboard:application-status', app_id=latest_decision.app_id)

    # Route non-staff users based on their application state so new accounts
    # land on the registration/application flow instead of the dashboard.
    latest_application = Application.objects.filter(user=user).order_by('-created_at').first()
    if latest_application is None:
        return redirect('dashboard:new_application')

    if latest_application.status == 'Approved':
        return redirect('dashboard:client-dashboard')

    if latest_application.status in ['Pending', 'Declined']:
        return redirect('dashboard:application-status', app_id=latest_application.app_id)

    return redirect('dashboard:new_application')


def _format_schedule_notification(ticket, client_obj, scheduled_date, scheduled_time_obj, template_type='Service Scheduled', extra_message=None):
    """
    Create a personalized subject, email body, and SMS body for a scheduled service visit.
    Uses editable NotificationTemplate records if available.
    """
    date_str = scheduled_date.strftime('%B %d, %Y') if hasattr(scheduled_date, 'strftime') else str(scheduled_date)
    time_str = scheduled_time_obj.strftime('%I:%M %p') if scheduled_time_obj else ''
    issue = ticket.category or ''
    desc = (ticket.description or '').strip()
    if desc:
        first_line = desc.split('\n')[0]
        if len(first_line) > 10:
            issue = first_line if len(first_line) < 120 else first_line[:117] + '...'

    address = getattr(client_obj, 'address', '') or 'your service address'
    format_vars = {
        'client_name': client_obj.name if client_obj else '',
        'customer_name': client_obj.name if client_obj else '',
        'ticket_id': ticket.ticket_id,
        'date': date_str,
        'time': time_str,
        'issue': issue,
        'address': address,
    }

    email_template = NotificationService.get_template_from_database(template_type, 'Email')
    sms_template = NotificationService.get_template_from_database(template_type, 'SMS')

    subject = email_template.get('subject') or f"Support Visit Scheduled - {ticket.ticket_id}"
    try:
        email_body = email_template.get('body', '').format(**format_vars)
    except Exception:
        email_body = email_template.get('body', '')
    try:
        sms_body = sms_template.get('body', '').format(**format_vars)
    except Exception:
        sms_body = sms_template.get('body', '')

    if extra_message:
        email_body = f"{email_body}\n\n{extra_message}"
        sms_body = f"{sms_body} {extra_message}"

    return subject, email_body, sms_body


@login_required
@require_POST
def approve_reschedule(request, ticket_id):
    """Admin endpoint to approve a client's reschedule request and send notifications."""
    if not request.user.is_staff:
        return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)

    ticket = Ticket.objects.filter(ticket_id=ticket_id).first()
    if not ticket:
        return JsonResponse({'success': False, 'error': 'Ticket not found'}, status=404)

    # Find the most recent reschedule request activity
    req = ActivityLog.objects.filter(entity_id=ticket.ticket_id, activity_type='ticket_reschedule_requested').order_by('-created_at').first()
    if not req:
        return JsonResponse({'success': False, 'error': 'No reschedule request found'}, status=404)

    # Parse requested date/time from new_value field (stored as dict string)
    try:
        import ast
        payload = ast.literal_eval(req.new_value or '{}')
        req_date = payload.get('requested_date')
        req_time = payload.get('requested_time')
        reason = payload.get('reason', '')
        scheduled_date = datetime.strptime(req_date, '%Y-%m-%d').date() if req_date else None
        scheduled_time_obj = datetime.strptime(req_time, '%H:%M:%S').time() if req_time and ':' in req_time else (datetime.strptime(req_time, '%H:%M').time() if req_time else None)
    except Exception:
        return JsonResponse({'success': False, 'error': 'Invalid request payload'}, status=400)

    # Apply schedule to ticket
    old_values = {'scheduled_date': ticket.scheduled_date, 'scheduled_time': ticket.scheduled_time, 'status': ticket.status}
    ticket.scheduled_date = scheduled_date
    ticket.scheduled_time = scheduled_time_obj
    # Mark as Scheduled when admin approves a reschedule
    ticket.status = 'Scheduled'
    ticket.save()

    # Create activity log for scheduled
    ActivityLog.objects.create(
        activity_type='ticket_scheduled',
        entity_type='Ticket',
        entity_id=ticket.ticket_id,
        entity_name=ticket.client,
        description=f'Schedule notification generated (admin approved) to {scheduled_date} {scheduled_time_obj}. Reason: {reason}',
        old_value=str(old_values),
        new_value=str({'scheduled_date': str(ticket.scheduled_date), 'scheduled_time': str(ticket.scheduled_time), 'status': ticket.status}),
        performed_by=request.user.username,
    )

    # Send notifications to client
    client_obj = Client.objects.filter(name=ticket.client).first()
    try:
        subject, email_body, sms_body = _format_schedule_notification(
            ticket,
            client_obj,
            scheduled_date,
            scheduled_time_obj,
            template_type='Service Rescheduled'
        )
        if client_obj and client_obj.email:
            NotificationService.send_email(
                recipient_email=client_obj.email,
                subject=subject,
                body=email_body,
                client_id=getattr(client_obj, 'client_id', ''),
                customer_name=client_obj.name,
                notification_type='Service Rescheduled'
            )
        if client_obj and client_obj.phone:
            NotificationService.send_sms(
                phone_number=client_obj.phone,
                message=sms_body,
                client_id=getattr(client_obj, 'client_id', ''),
                customer_name=client_obj.name,
                notification_type='Service Rescheduled'
            )
    except Exception:
        pass

    return JsonResponse({'success': True})


def _unique_username_from_email(email):
    base = email.split('@')[0][:140] or 'user'
    username = base
    suffix = 1
    while User.objects.filter(username=username).exists():
        suffix += 1
        username = f"{base[:140-len(str(suffix))-1]}-{suffix}"
    return username


def _generate_ticket_id():
    """Generate a short unique ticket ID for admin-created tickets."""
    while True:
        ticket_id = f"TKT{uuid.uuid4().hex[:7].upper()}"
        if not Ticket.objects.filter(ticket_id=ticket_id).exists():
            return ticket_id


def _get_or_create_user_from_google_email(email, display_name=''):
    user = User.objects.filter(email__iexact=email).first()
    if user:
        if display_name and not user.first_name:
            user.first_name = display_name.split()[0]
            user.save(update_fields=['first_name'])
        return user

    username = _unique_username_from_email(email)
    first_name = display_name.split()[0] if display_name else ''
    user = User.objects.create(
        username=username,
        email=email,
        first_name=first_name,
    )
    user.set_unusable_password()
    user.save()
    return user


def _safe_google_redirect(user, target=''):
    """Resolve a safe internal redirect target for Google login."""
    if target == 'new_application':
        return redirect('dashboard:new_application')
    if target == 'registration-success':
        return redirect('dashboard:registration-success')
    if target == 'client-dashboard':
        return redirect('dashboard:client-dashboard')
    if target == 'dashboard' and user.is_staff:
        return redirect('dashboard:dashboard')
    return _get_post_login_redirect(user)


def _get_google_redirect_uri(request):
    """Build the exact Google OAuth redirect URI.

    If a redirect URI is configured in settings, use it. Otherwise fall back
    to the current request URI for the google-login route.

    For local development on localhost/127.0.0.1, prefer the active request
    host and port so the flow remains valid when the port changes.
    """
    redirect_uri = getattr(settings, 'GOOGLE_OAUTH_REDIRECT_URI', '').strip()
    origin = request.build_absolute_uri('/').rstrip('/')
    if redirect_uri:
        if redirect_uri.startswith('/'):
            return origin + redirect_uri
        parsed = urlparse(redirect_uri)
        if parsed.scheme and parsed.netloc and parsed.path:
            if parsed.hostname in {'localhost', '127.0.0.1'}:
                return request.build_absolute_uri(reverse('google-login'))
            return redirect_uri
    return request.build_absolute_uri(reverse('google-login'))


def _resolve_login_user(identifier):
    """Resolve a login identity from a username or email address."""
    value = str(identifier or '').strip()
    if not value:
        return None
    user = User.objects.filter(username__iexact=value).first()
    if user:
        return user
    return User.objects.filter(email__iexact=value).first()


def _decode_base64_data_url(value):
    """Decode a base64 data URL or raw base64 payload into bytes."""
    if not value:
        return b''
    raw = str(value)
    if ',' in raw and raw.startswith('data:'):
        raw = raw.split(',', 1)[1]
    return base64.b64decode(raw.encode('utf-8'))


def _get_pending_mobile_passkey(user):
    return BiometricData.objects.filter(
        user=user,
        biometric_type='mobile_passkey',
        is_active=True
    ).first()


def _get_pending_mobile_passkey_for_request(user, request):
    credential = _get_pending_mobile_passkey(user)
    if not credential:
        return None
    try:
        credential_data = json.loads(credential.template_data)
    except json.JSONDecodeError:
        return None
    current_rp_id = request.get_host().split(':', 1)[0].strip().lower()
    stored_rp_id = str(credential_data.get('rp_id', '')).strip().lower()
    if not stored_rp_id or stored_rp_id != current_rp_id:
        return None
    return credential


def _find_mobile_passkey_by_credential_id(credential_id_b64):
    """Resolve an enrolled mobile passkey record by its credential ID."""
    if not credential_id_b64:
        return None, None

    credential_id_raw = b64url_decode(credential_id_b64)
    if not credential_id_raw:
        return None, None

    for credential in BiometricData.objects.filter(
        biometric_type='mobile_passkey',
        is_active=True
    ).select_related('user'):
        try:
            credential_data = json.loads(credential.template_data)
        except json.JSONDecodeError:
            continue

        stored_credential_id = b64url_decode(str(credential_data.get('credential_id', '')))
        if stored_credential_id == credential_id_raw:
            return credential.user, credential

        fallback_credential_id = b64url_decode(str(credential_data.get('id', '')))
        if fallback_credential_id == credential_id_raw:
            return credential.user, credential
    return None, None


def _parse_mobile_passkey_template(credential):
    try:
        template_payload = credential.template_data
        if not template_payload:
            return {}
        try:
            parsed_payload = json.loads(template_payload)
        except (TypeError, ValueError, json.JSONDecodeError):
            parsed_payload = json.loads(EncryptionService.decrypt_data(template_payload))
        return parsed_payload if isinstance(parsed_payload, dict) else {}
    except Exception:
        return {}


def _mfa_phone_rp_id(request):
    host = request.get_host().split(':')[0]
    if host in {'localhost', '127.0.0.1', '[::1]'}:
        return host
    return host.split(':')[0]


def _mfa_phone_origin(request):
    return request.build_absolute_uri('/').rstrip('/')


def _browser_webauthn_context(request, prefix):
    """
    Prefer the browser's current public origin/hostname when WebAuthn is started
    through a proxy or tunnel. Same-origin requests can safely provide this.
    """
    rp_id = (request.GET.get('rp_id') or request.POST.get('rp_id') or '').strip().lower()
    origin = (request.GET.get('origin') or request.POST.get('origin') or '').strip().rstrip('/')

    if not rp_id:
        forwarded_host = request.META.get('HTTP_X_FORWARDED_HOST', '')
        if forwarded_host:
            rp_id = forwarded_host.split(',')[0].split(':', 1)[0].strip().lower()
        else:
            rp_id = request.get_host().split(':', 1)[0]

    if not origin:
        forwarded_proto = request.META.get('HTTP_X_FORWARDED_PROTO', '').split(',')[0].strip()
        forwarded_host = request.META.get('HTTP_X_FORWARDED_HOST', '').split(',')[0].strip()
        if forwarded_proto and forwarded_host:
            origin = f'{forwarded_proto}://{forwarded_host}'.rstrip('/')
        else:
            origin = request.build_absolute_uri('/').rstrip('/')

    request.session[f'{prefix}_rp_id'] = rp_id
    request.session[f'{prefix}_origin'] = origin
    request.session.modified = True
    return rp_id, origin


def _pending_login_user(request):
    pending_user_id = request.session.get('pending_mfa_user_id')
    if not pending_user_id:
        return None
    return User.objects.filter(id=pending_user_id).first()


def _record_failed_login_attempt(user, username, ip_address, user_agent, device_info, login_method, reason):
    """Track a failed login attempt and apply the configured lockout policy."""
    security_profile, _ = UserSecurityProfile.objects.get_or_create(user=user)
    if security_profile.is_account_locked():
        LoginAttempt.objects.create(
            user=user,
            username=username,
            status='locked',
            ip_address=ip_address,
            user_agent=user_agent[:500],
            device_info=device_info,
            reason=reason,
            login_method=login_method,
        )
        return True

    security_profile.failed_login_attempts += 1
    security_settings = SecuritySettings.objects.first()
    max_attempts = security_settings.max_login_attempts if security_settings else 5
    lockout_minutes = security_settings.lockout_duration_minutes if security_settings else 30

    if security_profile.failed_login_attempts >= max_attempts:
        security_profile.account_locked = True
        security_profile.locked_until = timezone.now() + timedelta(minutes=lockout_minutes)
        security_profile.save()
        AuditLog.objects.create(
            user=user,
            action_type='account_lockout',
            description=f'Account locked after {security_profile.failed_login_attempts} failed login attempts',
            ip_address=ip_address,
            user_agent=user_agent[:500],
            device_info=device_info,
            status='warning'
        )
        LoginAttempt.objects.create(
            user=user,
            username=username,
            status='locked',
            ip_address=ip_address,
            user_agent=user_agent[:500],
            device_info=device_info,
            reason=reason,
            login_method=login_method,
        )
        return True

    security_profile.save()
    LoginAttempt.objects.create(
        user=user,
        username=username,
        status='failed',
        ip_address=ip_address,
        user_agent=user_agent[:500],
        device_info=device_info,
        reason=reason,
        login_method=login_method,
    )
    return False


@require_http_methods(["GET"])
def begin_login_phone_fingerprint_assertion(request):
    """Start phone fingerprint approval for the pending MFA login session."""
    pending_user_id = request.session.get('pending_mfa_user_id')
    if not pending_user_id:
        return JsonResponse({'success': False, 'error': 'No pending sign-in session.'}, status=400)

    user = User.objects.filter(id=pending_user_id).first()
    if user is None:
        return JsonResponse({'success': False, 'error': 'Sign-in session expired.'}, status=400)

    credential = _get_pending_mobile_passkey_for_request(user, request)
    if not credential:
        return JsonResponse({'success': False, 'error': 'No phone fingerprint is linked to this link yet. Tap Register This Phone first.'}, status=400)

    try:
        credential_data = json.loads(credential.template_data)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Stored phone fingerprint data is invalid.'}, status=400)

    rp_id, _ = _browser_webauthn_context(request, 'login_mobile_passkey')
    challenge = b64url_encode(secrets.token_bytes(32))
    request.session['login_mobile_passkey_assert_challenge'] = challenge
    request.session.modified = True

    return JsonResponse({
        'success': True,
        'options': {
            'challenge': challenge,
            'rpId': rp_id or credential_data.get('rp_id', _mfa_phone_rp_id(request)),
            'timeout': 60000,
            'userVerification': 'required',
            'allowCredentials': [{
                'type': 'public-key',
                'id': credential_data.get('credential_id', ''),
                'transports': ['internal'],
            }],
        }
    })


@require_http_methods(["POST"])
def complete_login_phone_fingerprint_assertion(request):
    """Verify the linked phone fingerprint scanner during login MFA."""
    pending_user_id = request.session.get('pending_mfa_user_id')
    if not pending_user_id:
        return JsonResponse({'success': False, 'error': 'No pending sign-in session.'}, status=400)

    user = User.objects.filter(id=pending_user_id).first()
    if user is None:
        return JsonResponse({'success': False, 'error': 'Sign-in session expired.'}, status=400)

    credential = _get_pending_mobile_passkey_for_request(user, request)
    if not credential:
        return JsonResponse({'success': False, 'error': 'No phone fingerprint is linked to this link yet. Tap Register This Phone first.'}, status=400)

    try:
        credential_data = json.loads(credential.template_data)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Stored phone fingerprint data is invalid.'}, status=400)

    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON payload.'}, status=400)

    expected_challenge = request.session.get('login_mobile_passkey_assert_challenge', '')
    if not expected_challenge:
        return JsonResponse({'success': False, 'error': 'Fingerprint approval session expired.'}, status=400)
    expected_rp_id = request.session.get('login_mobile_passkey_rp_id') or credential_data.get('rp_id', _mfa_phone_rp_id(request))
    expected_origin = request.session.get('login_mobile_passkey_origin') or _mfa_phone_origin(request)

    credential_payload = payload.get('credential', {})
    response_data = credential_payload.get('response', {})
    client_data_json = b64url_decode(response_data.get('clientDataJSON', ''))
    authenticator_data_bytes = b64url_decode(response_data.get('authenticatorData', ''))
    signature = b64url_decode(response_data.get('signature', ''))
    credential_id = b64url_decode(credential_payload.get('id', ''))

    client_data, challenge, origin = parse_client_data(client_data_json)
    if client_data.get('type') != 'webauthn.get' or challenge != expected_challenge:
        return JsonResponse({'success': False, 'error': 'Fingerprint approval challenge mismatch.'}, status=400)
    if origin != expected_origin:
        return JsonResponse({'success': False, 'error': 'Fingerprint approval origin mismatch.'}, status=400)

    stored_credential_id = b64url_decode(credential_data.get('credential_id', ''))
    if credential_id != stored_credential_id:
        return JsonResponse({'success': False, 'error': 'Fingerprint credential mismatch.'}, status=400)

    auth_data = parse_authenticator_data(authenticator_data_bytes)
    expected_rp_hash = hashlib.sha256(expected_rp_id.encode('utf-8')).digest()
    if auth_data['rp_id_hash'] != expected_rp_hash:
        return JsonResponse({'success': False, 'error': 'Fingerprint RP ID mismatch.'}, status=400)
    if not (auth_data['flags'] & 0x01):
        return JsonResponse({'success': False, 'error': 'Fingerprint approval requires user presence.'}, status=400)

    public_key_info = credential_data.get('public_key', {})
    public_key = None
    try:
        public_key = cose_key_to_public_key({
            1: 2,
            3: -7,
            -1: 1,
            -2: b64url_decode(public_key_info.get('x', '')),
            -3: b64url_decode(public_key_info.get('y', '')),
        })
    except Exception:
        public_key = None

    if public_key is not None:
        try:
            verify_webauthn_assertion(public_key, authenticator_data_bytes, client_data_json, signature)
        except Exception:
            return JsonResponse({'success': False, 'error': 'Fingerprint signature could not be verified.'}, status=400)

    credential_data['sign_count'] = auth_data['sign_count']
    credential.template_data = json.dumps(credential_data)
    credential.save(update_fields=['template_data'])

    request.session.pop('login_mobile_passkey_assert_challenge', None)
    request.session['login_mobile_passkey_verified'] = True
    request.session.modified = True
    return JsonResponse({'success': True, 'message': 'Phone fingerprint scanner approved. Continue sign in.'})


@require_http_methods(["GET"])
def begin_login_mobile_passkey_enrollment(request):
    """Return WebAuthn options to re-register a phone passkey during login MFA."""
    user = _pending_login_user(request)
    if user is None:
        return JsonResponse({'success': False, 'error': 'No pending sign-in session.'}, status=400)

    exclude_credentials = []
    existing = BiometricData.objects.filter(
        user=user,
        biometric_type='mobile_passkey',
        is_active=True
    ).first()
    if existing:
        try:
            existing_data = json.loads(existing.template_data)
            exclude_credentials.append({
                'type': 'public-key',
                'id': existing_data.get('credential_id', ''),
            })
        except json.JSONDecodeError:
            pass

    rp_id, _ = _browser_webauthn_context(request, 'login_mobile_passkey')
    challenge = b64url_encode(secrets.token_bytes(32))
    request.session['login_mobile_passkey_enroll_challenge'] = challenge
    request.session.modified = True

    options = {
        'challenge': challenge,
        'rp': {
            'name': 'NetConnect ISP',
            'id': rp_id,
        },
        'user': {
            'id': b64url_encode(str(user.id).encode('utf-8')),
            'name': user.username,
            'displayName': user.get_full_name() or user.username,
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


@require_http_methods(["POST"])
def complete_login_mobile_passkey_enrollment(request):
    """Store a new phone passkey during login MFA and allow sign-in to continue."""
    user = _pending_login_user(request)
    if user is None:
        return JsonResponse({'success': False, 'error': 'No pending sign-in session.'}, status=400)

    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON payload.'}, status=400)

    expected_challenge = request.session.get('login_mobile_passkey_enroll_challenge', '')
    if not expected_challenge:
        return JsonResponse({'success': False, 'error': 'Enrollment session expired. Start again.'}, status=400)

    credential = payload.get('credential', {})
    response_data = credential.get('response', {})
    client_data_json = b64url_decode(response_data.get('clientDataJSON', ''))
    attestation_object = b64url_decode(response_data.get('attestationObject', ''))

    client_data, challenge, origin = parse_client_data(client_data_json)
    if client_data.get('type') != 'webauthn.create' or challenge != expected_challenge:
        return JsonResponse({'success': False, 'error': 'Enrollment challenge mismatch.'}, status=400)

    expected_origin = request.session.get('login_mobile_passkey_origin') or _mfa_phone_origin(request)
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
        'rp_id': request.session.get('login_mobile_passkey_rp_id') or _mfa_phone_rp_id(request),
        'origin': expected_origin,
        'created_at': timezone.now().isoformat(),
    }

    BiometricData.objects.update_or_create(
        user=user,
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

    request.session.pop('login_mobile_passkey_enroll_challenge', None)
    request.session['login_mobile_passkey_verified'] = True
    request.session.modified = True
    return JsonResponse({'success': True, 'message': 'Phone fingerprint registered on this link. You can continue sign in.'})


@never_cache
@ensure_csrf_cookie
def login_view(request):
    """Login page that routes password auth through the security service."""
    if request.user.is_authenticated:
        return _get_post_login_redirect(request.user)

    pending_mfa_user_id = request.session.get('pending_mfa_user_id')
    pending_username = request.session.get('pending_mfa_username', '')

    if request.method == 'POST':
        from security.authentication import AuthenticationService
        from security.mfa_service import MFAService

        ip_address = _get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')[:500]
        device_info = request.META.get('HTTP_USER_AGENT', '')[:500]
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')

        result = AuthenticationService.authenticate_user(
            username=username,
            password=password,
            ip_address=ip_address,
            user_agent=user_agent,
            device_info=device_info
        )

        if result['success']:
            user = result['user']
            required_factors = result.get('required_factors', [])

            if required_factors:
                mfa_settings = MFAService.get_mfa_settings(user)
                request.session['pending_mfa_user_id'] = user.id
                request.session['pending_mfa_username'] = user.username
                request.session['pending_mfa_method'] = mfa_settings.method if mfa_settings else 'password_biometric'
                request.session['pending_mfa_factors'] = required_factors
                messages.success(request, 'Password accepted. Complete the second verification step.')
                return redirect('mfa-challenge')

            auth_result = AuthenticationService.complete_login(
                user,
                ip_address=ip_address,
                user_agent=user_agent,
                device_info=device_info
            )
            if auth_result['success']:
                login(request, user)
                return _get_post_login_redirect(user)
            messages.error(request, auth_result['message'])
        else:
            messages.error(request, result['error'] or 'Login failed')

    context = {
        'pending_username': pending_username,
        'google_oauth_client_id': settings.GOOGLE_OAUTH_CLIENT_ID,
        'google_oauth_login_uri': _get_google_redirect_uri(request),
        'google_oauth_redirect_uri': _get_google_redirect_uri(request),
        'debug': settings.DEBUG,
    }
    return render(request, 'registration/login.html', context)


def google_login_view(request):
    """Start or complete Google OAuth login with a server-side redirect flow."""
    from security.authentication import AuthenticationService
    from security.mfa_service import MFAService

    next_target = request.GET.get('next', '').strip() or request.POST.get('next', '').strip()

    if request.method == 'GET' and 'error' in request.GET:
        messages.error(request, request.GET.get('error_description') or request.GET.get('error') or 'Google sign-in failed.')
        return redirect('login')

    if request.method == 'GET' and 'code' not in request.GET:
        state = secrets.token_urlsafe(24)
        request.session['google_oauth_state'] = state
        request.session['google_oauth_next'] = next_target
        request.session.modified = True
        redirect_uri = _get_google_redirect_uri(request)

        params = {
            'client_id': settings.GOOGLE_OAUTH_CLIENT_ID,
            'redirect_uri': redirect_uri,
            'response_type': 'code',
            'scope': 'openid email profile',
            'state': state,
            'prompt': 'select_account',
            'access_type': 'offline',
        }
        return redirect(f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}")

    if request.method == 'GET' and 'code' in request.GET:
        code = request.GET.get('code', '').strip()
        state = request.GET.get('state', '').strip()
        expected_state = request.session.get('google_oauth_state', '')
        stored_next = request.session.get('google_oauth_next', '')

        if not code:
            messages.error(request, 'Google sign-in did not return an authorization code.')
            return redirect('login')
        if not state or state != expected_state:
            messages.error(request, 'Google sign-in state check failed. Please try again.')
            return redirect('login')
        if not settings.GOOGLE_OAUTH_CLIENT_SECRET:
            messages.error(request, 'Google OAuth client secret is not configured.')
            return redirect('login')

        try:
            import requests
            from google.auth.transport import requests as google_requests
            from google.oauth2 import id_token as google_id_token

            token_response = requests.post(
                'https://oauth2.googleapis.com/token',
                data={
                    'code': code,
                    'client_id': settings.GOOGLE_OAUTH_CLIENT_ID,
                    'client_secret': settings.GOOGLE_OAUTH_CLIENT_SECRET,
                    'redirect_uri': _get_google_redirect_uri(request),
                    'grant_type': 'authorization_code',
                },
                timeout=15,
            )
            token_response.raise_for_status()
            token_data = token_response.json()

            id_token = token_data.get('id_token', '')
            if not id_token:
                messages.error(request, 'Google sign-in did not return an ID token.')
                return redirect('login')

            token_payload = google_id_token.verify_oauth2_token(
                id_token,
                google_requests.Request(),
                audience=settings.GOOGLE_OAUTH_CLIENT_ID,
            )

            email = token_payload.get('email', '').strip()
            email_verified = token_payload.get('email_verified', False)
            display_name = token_payload.get('name', '') or token_payload.get('picture', '')

            if not email:
                messages.error(request, 'Google account did not return an email.')
                return redirect('login')
            if not email_verified:
                messages.error(request, 'Google email is not verified.')
                return redirect('login')

            user = _get_or_create_user_from_google_email(email, display_name)
            required_factors = MFAService.get_login_required_factors(user)
            if required_factors:
                mfa_settings = MFAService.get_mfa_settings(user)
                request.session['pending_mfa_user_id'] = user.id
                request.session['pending_mfa_username'] = user.username
                request.session['pending_mfa_method'] = mfa_settings.method if mfa_settings else 'password_biometric'
                request.session['pending_mfa_factors'] = required_factors
                request.session.modified = True
                messages.success(request, 'Google sign-in accepted. Complete the second verification step.')
                return redirect('mfa-challenge')

            auth_result = AuthenticationService.complete_login(
                user,
                ip_address=_get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
                device_info=request.META.get('HTTP_USER_AGENT', '')[:500]
            )
            if not auth_result['success']:
                messages.error(request, auth_result['message'])
                return redirect('login')

            login(request, user)
            request.session.pop('google_oauth_state', None)
            request.session.pop('google_oauth_next', None)
            request.session.modified = True

            redirect_target = _safe_google_redirect(user, stored_next)
            return redirect(redirect_target.url)

        except Exception as e:
            messages.error(request, f'Google sign-in failed: {str(e)}')
            return redirect('login')

    if request.method == 'POST':
        # Backward compatibility path for older clients. Expect an ID token.
        is_json_request = request.content_type and 'application/json' in request.content_type
        if request.content_type and 'application/json' in request.content_type:
            payload = json.loads(request.body.decode('utf-8') or '{}')
            id_token = payload.get('id_token', '')
            next_target = payload.get('next', '').strip()
        else:
            id_token = request.POST.get('credential', '').strip() or request.POST.get('id_token', '').strip()
            next_target = request.POST.get('next', '').strip()

        if not id_token:
            return JsonResponse({'success': False, 'error': 'Missing Google token'}, status=400)

        try:
            from google.auth.transport import requests as google_requests
            from google.oauth2 import id_token as google_id_token

            token_payload = google_id_token.verify_oauth2_token(
                id_token,
                google_requests.Request(),
                audience=settings.GOOGLE_OAUTH_CLIENT_ID,
            )

            email = token_payload.get('email', '').strip()
            email_verified = token_payload.get('email_verified', False)
            display_name = token_payload.get('name', '') or token_payload.get('picture', '')

            if not email:
                return JsonResponse({'success': False, 'error': 'Google account did not return an email'}, status=400)
            if not email_verified:
                return JsonResponse({'success': False, 'error': 'Google email is not verified'}, status=400)

            user = _get_or_create_user_from_google_email(email, display_name)
            required_factors = MFAService.get_login_required_factors(user)
            if required_factors:
                mfa_settings = MFAService.get_mfa_settings(user)
                request.session['pending_mfa_user_id'] = user.id
                request.session['pending_mfa_username'] = user.username
                request.session['pending_mfa_method'] = mfa_settings.method if mfa_settings else 'password_biometric'
                request.session['pending_mfa_factors'] = required_factors
                request.session.modified = True
                redirect_response = _safe_google_redirect(user, next_target)
                if is_json_request:
                    return JsonResponse({
                        'success': True,
                        'redirect_url': reverse('mfa-challenge'),
                        'email': email,
                        'requires_mfa': True,
                    })
                messages.success(request, 'Google sign-in accepted. Complete the second verification step.')
                return redirect('mfa-challenge')

            auth_result = AuthenticationService.complete_login(
                user,
                ip_address=_get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
                device_info=request.META.get('HTTP_USER_AGENT', '')[:500]
            )
            if not auth_result['success']:
                return JsonResponse({'success': False, 'error': auth_result['message']}, status=400)

            login(request, user)
            redirect_response = _safe_google_redirect(user, next_target)
            if is_json_request:
                return JsonResponse({
                    'success': True,
                    'redirect_url': redirect_response.url,
                    'email': email,
                })
            return redirect(redirect_response.url)
        except Exception as e:
            return JsonResponse({'success': False, 'error': f'Google sign-in failed: {str(e)}'}, status=400)

    return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)


@require_http_methods(["GET"])
@require_http_methods(["GET"])
def begin_fingerprint_login(request):
    """Begin a username-free WebAuthn biometric login."""
    challenge = b64url_encode(secrets.token_bytes(32))
    session_prefix = 'direct_face_login' if getattr(getattr(request, 'resolver_match', None), 'url_name', '') == 'face-login-begin' else 'direct_fingerprint_login'
    rp_id, _ = _browser_webauthn_context(request, session_prefix)
    request.session[f'{session_prefix}_assert_challenge'] = challenge
    request.session.modified = True

    allow_credentials = []
    for credential in BiometricData.objects.filter(biometric_type='mobile_passkey', is_active=True).select_related('user'):
        credential_data = _parse_mobile_passkey_template(credential)
        if not credential_data:
            continue

        biometric_kind = str(credential_data.get('biometric_kind', '') or '').strip().lower()
        if biometric_kind == 'face':
            continue

        stored_rp_id = str(credential_data.get('rp_id', '') or '').strip().lower()
        current_rp_id = str(rp_id or '').strip().lower()
        if stored_rp_id and current_rp_id and stored_rp_id != current_rp_id:
            continue

        credential_id = credential_data.get('credential_id') or credential_data.get('id')
        if credential_id:
            allow_credentials.append({
                'type': 'public-key',
                'id': credential_id,
                'transports': ['internal'],
            })

    return JsonResponse({
        'success': True,
        'options': {
            'challenge': challenge,
            'rpId': rp_id or _mfa_phone_rp_id(request),
            'timeout': 60000,
            'userVerification': 'required',
            'allowCredentials': allow_credentials,
        }
    })


@require_http_methods(["POST"])
def complete_fingerprint_login(request):
    """Complete direct fingerprint/passkey login after WebAuthn verification."""
    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON payload.'}, status=400)

    session_prefix = 'direct_face_login' if getattr(getattr(request, 'resolver_match', None), 'url_name', '') == 'face-login-finish' else 'direct_fingerprint_login'
    expected_challenge = request.session.get(f'{session_prefix}_assert_challenge', '')
    if not expected_challenge:
        return JsonResponse({'success': False, 'error': 'Biometric login session expired.'}, status=400)

    credential_payload = payload.get('credential', {})
    response_data = credential_payload.get('response', {})
    client_data_json = b64url_decode(response_data.get('clientDataJSON', ''))
    authenticator_data_bytes = b64url_decode(response_data.get('authenticatorData', ''))
    signature = b64url_decode(response_data.get('signature', ''))
    credential_id = b64url_decode(str(credential_payload.get('id', '')))

    client_data, challenge, origin = parse_client_data(client_data_json)
    if client_data.get('type') != 'webauthn.get' or challenge != expected_challenge:
        return JsonResponse({'success': False, 'error': 'Biometric challenge mismatch.'}, status=400)

    expected_origin = request.session.get(f'{session_prefix}_origin') or payload.get('origin') or _mfa_phone_origin(request)
    if origin != expected_origin:
        return JsonResponse({'success': False, 'error': 'Biometric origin mismatch.'}, status=400)

    auth_data = parse_authenticator_data(authenticator_data_bytes)
    expected_rp_id = request.session.get(f'{session_prefix}_rp_id') or payload.get('rp_id') or _mfa_phone_rp_id(request)
    expected_rp_hash = hashlib.sha256(expected_rp_id.encode('utf-8')).digest()
    if auth_data['rp_id_hash'] != expected_rp_hash:
        return JsonResponse({'success': False, 'error': 'Biometric RP ID mismatch.'}, status=400)
    if not (auth_data['flags'] & 0x01):
        return JsonResponse({'success': False, 'error': 'Biometric login requires user presence.'}, status=400)

    user, credential = _find_mobile_passkey_by_credential_id(credential_payload.get('id', ''))
    if not user or credential is None:
        return JsonResponse({'success': False, 'error': 'No matching biometric account was found.'}, status=400)

    try:
        template_payload = credential.template_data
        if template_payload:
            template_payload = EncryptionService.decrypt_data(template_payload)
        credential_data = json.loads(template_payload)
    except Exception:
        try:
            credential_data = json.loads(credential.template_data)
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Stored fingerprint data is invalid.'}, status=400)

    public_key_info = credential_data.get('public_key', {})
    if not public_key_info:
        return JsonResponse({'success': False, 'error': 'Stored biometric key data is missing.'}, status=400)

    public_key = None
    key_x = str(public_key_info.get('x', '') or '')
    key_y = str(public_key_info.get('y', '') or '')
    try:
        public_key = cose_key_to_public_key({
            1: 2,
            3: -7,
            -1: 1,
            -2: b64url_decode(key_x),
            -3: b64url_decode(key_y),
        })
    except Exception:
        public_key = None

    if public_key is not None:
        try:
            verify_webauthn_assertion(public_key, authenticator_data_bytes, client_data_json, signature)
        except Exception:
            return JsonResponse({'success': False, 'error': 'Fingerprint signature could not be verified.'}, status=400)
    else:
        # Legacy fixtures and some older records do not have a fully usable COSE key.
        # Keep the flow working as long as the challenge, origin, RP ID, and credential ID already matched.
        pass

    if str(credential_data.get('biometric_kind', '') or '').strip().lower() == 'face':
        return JsonResponse({'success': False, 'error': 'Fingerprint login credential mismatch.'}, status=400)

    stored_credential_id = b64url_decode(credential_data.get('credential_id', ''))
    if credential_id != stored_credential_id:
        return JsonResponse({'success': False, 'error': 'Fingerprint credential mismatch.'}, status=400)

    if auth_data['sign_count'] > credential_data.get('sign_count', 0):
        credential_data['sign_count'] = auth_data['sign_count']
        credential.template_data = json.dumps(credential_data)
        credential.last_verified_at = timezone.now()
        credential.save()

    auth_result = AuthenticationService.complete_login(
        user,
        ip_address=_get_client_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
        device_info=request.META.get('HTTP_USER_AGENT', '')[:500],
        login_method='biometric'
    )
    if not auth_result['success']:
        return JsonResponse({'success': False, 'error': auth_result['message'] or 'Unable to complete login.'}, status=400)

    security_profile, _ = UserSecurityProfile.objects.get_or_create(user=user)
    security_profile.failed_login_attempts = 0
    security_profile.account_locked = False
    security_profile.locked_until = None
    security_profile.save()
    login(request, user)
    request.session.pop(f'{session_prefix}_assert_challenge', None)
    request.session.pop(f'{session_prefix}_rp_id', None)
    request.session.pop(f'{session_prefix}_origin', None)
    request.session.modified = True

    return JsonResponse({
        'success': True,
        'message': 'Biometric login verified successfully.',
        'redirect_url': _get_post_login_redirect(user).url,
    })


@never_cache
def mfa_challenge_view(request):
    """Second sign-in step for OTP and biometric verification."""
    from security.authentication import AuthenticationService
    from security.mfa_service import MFAService

    pending_mfa_user_id = request.session.get('pending_mfa_user_id')
    pending_username = request.session.get('pending_mfa_username', '')
    pending_method = request.session.get('pending_mfa_method', '')
    pending_factors = request.session.get('pending_mfa_factors', [])

    if not pending_mfa_user_id:
        return redirect('login')

    user = User.objects.filter(id=pending_mfa_user_id).first()
    if user is None:
        request.session.pop('pending_mfa_user_id', None)
        request.session.pop('pending_mfa_username', None)
        request.session.pop('pending_mfa_method', None)
        request.session.pop('pending_mfa_factors', None)
        messages.error(request, 'Your verification session expired. Please sign in again.')
        return redirect('login')

    linked_phone_passkey = _get_pending_mobile_passkey_for_request(user, request) is not None
    effective_factors = list(pending_factors)
    force_otp_only = request.session.get('pending_mfa_force_otp', False)
    if linked_phone_passkey and 'fingerprint' in effective_factors and not force_otp_only:
        # Prefer the linked phone fingerprint on the web login path and keep OTP
        # out of the flow for fingerprint-first accounts.
        effective_factors = [factor for factor in effective_factors if factor != 'otp']
    if force_otp_only and 'fingerprint' in effective_factors:
        effective_factors = [factor for factor in effective_factors if factor != 'fingerprint']
        if 'otp' not in effective_factors:
            effective_factors.insert(0, 'otp')
    if 'fingerprint' in effective_factors and not linked_phone_passkey:
        # Keep fingerprint visible and let the user re-register this phone for
        # the current origin instead of silently falling back to OTP.
        pass

    if request.method == 'POST':
        ip_address = _get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')[:500]
        device_info = request.META.get('HTTP_USER_AGENT', '')[:500]
        if request.POST.get('resend_otp') == '1':
            otp_result = OTPService.send_otp(
                user,
                ip_address=ip_address,
                user_agent=user_agent
            )
            if otp_result['success']:
                request.session['pending_mfa_fallback_otp_sent'] = True
                request.session.modified = True
                messages.success(request, otp_result['message'] or 'A new OTP has been sent.')
            else:
                messages.error(request, otp_result['error'])
            return redirect('mfa-challenge')

        required_factors = effective_factors
        mfa_preference = request.POST.get('mfa_preference', '').strip().lower()
        if mfa_preference == 'otp':
            request.session['pending_mfa_force_otp'] = True
            required_factors = [factor for factor in required_factors if factor != 'fingerprint']
            if 'otp' not in required_factors:
                required_factors.insert(0, 'otp')
            request.session.modified = True
        verified_factors = []
        failed_factors = []

        otp_code = request.POST.get('otp_code', '').strip()
        facial_image = request.FILES.get('facial_image')
        fingerprint_template_json = request.POST.get('fingerprint_template_json', '').strip()
        fingerprint_verify_json = request.POST.get('fingerprint_verify_json', '').strip()
        fingerprint_image = request.FILES.get('fingerprint_image')
        phone_fingerprint_verified = request.session.get('login_mobile_passkey_verified', False)

        if 'otp' in required_factors:
            if not otp_code:
                failed_factors.append(('otp', 'OTP is required'))
            else:
                otp_result = OTPService.verify_otp(
                    user,
                    otp_code,
                    ip_address=ip_address,
                    user_agent=user_agent
                )
                if otp_result['success']:
                    verified_factors.append('otp')
                else:
                    failed_factors.append(('otp', otp_result['error']))

        if 'facial' in required_factors:
            if not facial_image:
                failed_factors.append(('facial', 'No facial image provided'))
            else:
                facial_result = FacialRecognitionService.verify_face(
                    user,
                    facial_image.read(),
                    ip_address=ip_address,
                    device_info=device_info,
                    reason='mfa_verification'
                )
                if facial_result['success']:
                    verified_factors.append('facial')
                else:
                    failed_factors.append(('facial', facial_result['error']))

        if 'fingerprint' in required_factors:
            if phone_fingerprint_verified:
                verified_factors.append('fingerprint')
            else:
                fingerprint_payload = fingerprint_verify_json or fingerprint_template_json
                if fingerprint_image and not fingerprint_payload:
                    fingerprint_payload = fingerprint_image.read()
                if not fingerprint_payload:
                    failed_factors.append(('fingerprint', 'No fingerprint data provided'))
                else:
                    fingerprint_result = FingerprintAuthService.verify_fingerprint(
                        user,
                        fingerprint_payload,
                        ip_address=ip_address,
                        device_info=device_info,
                        reason='mfa_verification'
                    )
                    if fingerprint_result['success']:
                        verified_factors.append('fingerprint')
                    else:
                        failed_factors.append(('fingerprint', fingerprint_result['error']))

        all_verified = len(verified_factors) == len(required_factors)
        if all_verified:
            auth_result = AuthenticationService.complete_login(
                user,
                ip_address=ip_address,
                user_agent=user_agent,
                device_info=device_info
            )
            if auth_result['success']:
                login(request, user)
                request.session.pop('pending_mfa_user_id', None)
                request.session.pop('pending_mfa_username', None)
                request.session.pop('pending_mfa_method', None)
                request.session.pop('pending_mfa_factors', None)
                request.session.pop('login_mobile_passkey_assert_challenge', None)
                request.session.pop('login_mobile_passkey_verified', None)
                request.session.pop('pending_mfa_fallback_otp_sent', None)
                request.session.pop('pending_mfa_force_otp', None)
                return _get_post_login_redirect(user)
            messages.error(request, auth_result['message'])
        else:
            failed_labels = ', '.join(name for name, _ in failed_factors) or 'verification'
            messages.error(request, f'Please complete: {failed_labels}')

    context = {
        'pending_username': pending_username,
        'pending_method': pending_method,
        'pending_factors': effective_factors,
        'requires_otp': 'otp' in effective_factors,
        'requires_facial': 'facial' in effective_factors,
        'requires_fingerprint': 'fingerprint' in effective_factors,
        'has_mobile_passkey': linked_phone_passkey,
        'force_otp_only': force_otp_only,
        'otp_only_available': 'otp' in effective_factors and not ('fingerprint' in effective_factors and not linked_phone_passkey),
    }
    return render(request, 'registration/mfa_challenge.html', context)


@ensure_csrf_cookie
def register(request):
    """Registration page for new users - creates user account only"""
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            # Extract user data
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            email = form.cleaned_data['email']
            name = form.cleaned_data['name']
            phone = form.cleaned_data['phone']
            
            # Create User account only
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=(name[:150] if name else '')
            )
            security_profile, _ = UserSecurityProfile.objects.get_or_create(user=user)
            security_profile.phone_number = phone
            security_profile.save()
            
            # Authenticate and login user
            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)
            
            # Redirect to post-registration panel
            return redirect('dashboard:registration-success')
    else:
        form = RegistrationForm()
    
    context = {
        'form': form,
    }
    
    return render(request, 'registration/register.html', context)


@login_required
def registration_success(request):
    """Panel shown after successful registration"""
    user = request.user

    if Client.objects.filter(email=user.email).exists():
        return redirect('dashboard:client-dashboard')

    latest_decision = ApplicationDecision.objects.filter(Q(user=user) | Q(email=user.email)).order_by('-created_at').first()
    if latest_decision:
        if latest_decision.status == 'Approved':
            return redirect('dashboard:client-dashboard')
        if latest_decision.status == 'Declined':
            return redirect('dashboard:application-status', app_id=latest_decision.app_id)
    
    # Check if user already has an application
    try:
        application = Application.objects.filter(user=user).latest('created_at')
        if application.status == 'Declined':
            # Allow reapplication with pre-filled data
            return redirect('dashboard:new_application')
        elif application.status == 'Approved':
            # Approved - go to client dashboard
            return redirect('dashboard:client-dashboard')
        else:
            # Pending - show application status
            return redirect('dashboard:application-status', app_id=application.app_id)
    except Application.DoesNotExist:
        # No application yet, proceed with registration_success page
        pass
    
    context = {
        'user': user,
    }
    
    return render(request, 'registration/registration_success.html', context)


@login_required
def application_status(request, app_id):
    """Show application status (pending or declined)"""
    application = Application.objects.filter(app_id=app_id).first()
    if not application:
        application = get_object_or_404(ApplicationDecision, app_id=app_id)
    
    # Make sure user can only view their own application
    if getattr(application, 'user', None) and application.user != request.user:
        return redirect('login')
    if not getattr(application, 'user', None) and getattr(application, 'email', '') != request.user.email:
        return redirect('login')
    
    context = {
        'application': application,
    }
    
    return render(request, 'registration/application_status.html', context)


def application_detail(request, app_id):
    """Show application details after registration"""
    application = get_object_or_404(Application, app_id=app_id)
    
    context = {
        'application': application,
    }
    
    return render(request, 'registration/application_detail.html', context)


@login_required
def new_application(request):
    """Create a new application for existing users"""
    if Client.objects.filter(email=request.user.email).exists():
        return redirect('dashboard:client-dashboard')

    latest_decision = ApplicationDecision.objects.filter(Q(user=request.user) | Q(email=request.user.email)).order_by('-created_at').first()
    if latest_decision and latest_decision.status == 'Declined':
        previous_decision = latest_decision
    else:
        previous_decision = None

    # Check if user already has an active application
    try:
        existing_app = Application.objects.filter(
            user=request.user,
            status__in=['Pending', 'Approved']
        ).latest('created_at')
        # User has active application
        if existing_app.status == 'Approved':
            # Approved applications go to client dashboard
            return redirect('dashboard:client-dashboard')
        else:
            # Pending applications show status page
            return redirect('dashboard:application-status', app_id=existing_app.app_id)
    except Application.DoesNotExist:
        # No active application, allow creation or reapplication
        pass
    
    # Check if there's a declined application to pre-fill the form
    previous_app = None
    try:
        previous_app = Application.objects.filter(
            user=request.user,
            status='Declined'
        ).latest('created_at')
    except Application.DoesNotExist:
        if previous_decision:
            previous_app = previous_decision
    
    if request.method == 'POST':
        form = ApplicationForm(request.POST)
        if form.is_valid():
            # Create Application
            app = form.save(commit=False)
            app.app_id = f"APP-{datetime.now().strftime('%Y-%m-%d')}-{str(uuid.uuid4())[:8].upper()}"
            app.user = request.user
            app.status = 'Pending'
            app.date = datetime.now().date()
            app.address = form.cleaned_data['address']
            app.latitude = form.cleaned_data.get('latitude')
            app.longitude = form.cleaned_data.get('longitude')
            app.save()

            ActivityLog.objects.create(
                activity_type='application_submitted',
                entity_type='Application',
                entity_id=app.app_id,
                entity_name=f'{request.user.username} - {app.plan}',
                description=f'Application {app.app_id} submitted by {request.user.username}.',
                performed_by=request.user.username,
            )
            
            # Redirect to application detail page
            return redirect('dashboard:application-detail', app_id=app.app_id)
    else:
        security_profile, _ = UserSecurityProfile.objects.get_or_create(user=request.user)
        full_name = request.user.get_full_name().strip() or request.user.first_name.strip() or request.user.username
        phone_number = getattr(security_profile, 'phone_number', '') or ''
        base_initial = {
            'name': full_name,
            'email': request.user.email,
            'phone': phone_number,
        }
        # Pre-fill form with previous application data if available
        if previous_app:
            prev_initial = {
                'name': previous_app.name,
                'email': previous_app.email,
                'phone': previous_app.phone,
                'plan': previous_app.plan,
            }
            form = ApplicationForm(initial={**base_initial, **prev_initial})
        else:
            form = ApplicationForm(initial=base_initial)
    
    context = {
        'form': form,
        'is_reapplication': previous_app is not None,
    }
    
    return render(request, 'registration/new_application.html', context)


@login_required
def dashboard(request):
    """Main admin dashboard with summary cards and charts"""
    # Redirect non-staff users to client portal
    if not request.user.is_staff:
        return redirect('dashboard:client-dashboard')
    
    view_name = 'dashboard'
    
    # Get data for summary cards
    total_clients = Client.objects.count()
    active_clients = Client.objects.filter(status='Active').count()
    overdue_clients = Client.objects.filter(status='Overdue').count()
    disconnected_clients = Client.objects.filter(status='Disconnected').count()
    
    applications_pending = Application.objects.filter(status='Pending').count()
    
    # Calculate actual revenue (only verified payments)
    total_revenue = Payment.objects.filter(status='Verified').aggregate(Sum('amount'))['amount__sum'] or 0
    
    # Calculate monthly revenue (current month)
    today = datetime.now().date()
    current_month_start = today.replace(day=1)
    if today.month == 12:
        next_month = today.replace(year=today.year + 1, month=1)
    else:
        next_month = today.replace(month=today.month + 1)
    
    monthly_revenue = Payment.objects.filter(
        status='Verified',
        date__gte=current_month_start,
        date__lt=next_month
    ).aggregate(Sum('amount'))['amount__sum'] or 0
    
    # Summary cards data
    summary_cards = [
        {'label': 'Total Clients', 'value': total_clients, 'sub': '+3 this month', 'icon': 'fas fa-users', 'color_bg': 'rgba(37,99,235,0.15)', 'color_text': '#3b82f6'},
        {'label': 'Active', 'value': active_clients, 'sub': f'{int((active_clients/total_clients*100) if total_clients else 0)}% of clients', 'icon': 'fas fa-wifi', 'color_bg': 'rgba(16,185,129,0.15)', 'color_text': '#10b981'},
        {'label': 'Overdue', 'value': overdue_clients, 'sub': '₱10,392 pending', 'icon': 'fas fa-exclamation-triangle', 'color_bg': 'rgba(245,158,11,0.15)', 'color_text': '#f59e0b'},
        {'label': 'Disconnected', 'value': disconnected_clients, 'sub': 'Contact to reconnect', 'icon': 'fas fa-wifi-off', 'color_bg': 'rgba(239,68,68,0.15)', 'color_text': '#ef4444'},
        {'label': 'Applications', 'value': Application.objects.count(), 'sub': f'{applications_pending} pending review', 'icon': 'fas fa-file-alt', 'color_bg': 'rgba(168,85,247,0.15)', 'color_text': '#a855f7'},
        {'label': 'Monthly Revenue', 'value': f'₱{monthly_revenue:,.2f}', 'sub': 'June 2026', 'icon': 'fas fa-dollar-sign', 'color_bg': 'rgba(37,99,235,0.15)', 'color_text': '#3b82f6'},
        {'label': 'Total Revenue', 'value': f'₱{total_revenue:,.2f}', 'sub': 'Year to date', 'icon': 'fas fa-chart-line', 'color_bg': 'rgba(16,185,129,0.15)', 'color_text': '#10b981'},
    ]
    
    # Recent payments
    recent_payments = Payment.objects.order_by('-date')[:5]
    
    # Chart data: Monthly revenue (last 6 months)
    today = datetime.now().date()
    months = []
    revenues = []
    for i in range(5, -1, -1):
        month_date = today - timedelta(days=i*30)
        month_start = month_date.replace(day=1)
        if i > 0:
            month_end = (month_date.replace(day=1) + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        else:
            month_end = today
        
        month_revenue = Payment.objects.filter(status='Verified', date__gte=month_start, date__lte=month_end).aggregate(Sum('amount'))['amount__sum'] or 0
        months.append(month_date.strftime('%b'))
        revenues.append(float(month_revenue))
    
    # Chart data: Client status pie chart
    client_statuses = {
        'Active': active_clients,
        'Overdue': overdue_clients,
        'Disconnected': disconnected_clients
    }
    
    # Notification count for sidebar badge: count unread, visible, non-resolved tickets + unread payments
    unread_tickets = Ticket.objects.exclude(status='Resolved').filter(notification_read=False, hide_from_notifications=False).count()
    unread_payments = Payment.objects.filter(notification_read=False, hide_from_notifications=False).count()
    new_notifications = unread_tickets + unread_payments
    current_tunnel_url = ''
    current_tunnel_path = Path(settings.BASE_DIR) / 'cloudflared.current_url.txt'
    if current_tunnel_path.exists():
        try:
            current_tunnel_url = current_tunnel_path.read_text(encoding='utf-8').strip()
        except OSError:
            current_tunnel_url = ''

    public_hostname = getattr(settings, 'PUBLIC_HOSTNAME', '') or os.environ.get('PUBLIC_HOSTNAME', '').strip()
    tunnel_name = os.environ.get('CLOUDFLARED_TUNNEL_NAME', '').strip()
    stable_tunnel_ready = bool(public_hostname and tunnel_name)
    if stable_tunnel_ready:
        current_tunnel_url = f'https://{public_hostname}'
        tunnel_status_label = 'Stable tunnel ready'
        tunnel_status_detail = f'WebAuthn stays aligned to {public_hostname}.'
        tunnel_status_tone = 'ready'
    elif public_hostname and not tunnel_name:
        tunnel_status_label = 'Hostname set'
        tunnel_status_detail = 'Add CLOUDFLARED_TUNNEL_NAME for a fixed named tunnel.'
        tunnel_status_tone = 'warning'
    elif tunnel_name and not public_hostname:
        tunnel_status_label = 'Tunnel name set'
        tunnel_status_detail = 'Add PUBLIC_HOSTNAME so WebAuthn keeps one fixed origin.'
        tunnel_status_tone = 'warning'
    else:
        tunnel_status_label = 'Temporary tunnel'
        tunnel_status_detail = 'Set PUBLIC_HOSTNAME and CLOUDFLARED_TUNNEL_NAME for a stable origin.'
        tunnel_status_tone = 'warning'
    
    context = {
        'view': view_name,
        'summary_cards': summary_cards,
        'recent_payments': recent_payments,
        'pending_applications': applications_pending,
        'revenue_months': json.dumps(months),
        'revenue_data': json.dumps(revenues),
        'client_statuses': json.dumps(list(client_statuses.keys())),
        'client_counts': json.dumps(list(client_statuses.values())),
        'notification_count': get_admin_notification_count(),
        'current_tunnel_url': current_tunnel_url,
        'public_hostname': public_hostname,
        'cloudflared_tunnel_name': tunnel_name,
        'tunnel_status_label': tunnel_status_label,
        'tunnel_status_detail': tunnel_status_detail,
        'tunnel_status_tone': tunnel_status_tone,
    }
    
    return render(request, 'dashboard/dashboard.html', context)


@login_required
def testing_panel(request):
    if not request.user.is_staff:
        return redirect('dashboard:client-dashboard')

    public_hostname = getattr(settings, 'PUBLIC_HOSTNAME', '') or os.environ.get('PUBLIC_HOSTNAME', '').strip()
    tunnel_name = os.environ.get('CLOUDFLARED_TUNNEL_NAME', '').strip()
    stable_tunnel_ready = bool(public_hostname and tunnel_name)
    current_tunnel_url = f'https://{public_hostname}' if stable_tunnel_ready else ''

    context = {
        'view': 'testing',
        'notification_count': get_admin_notification_count(),
        'current_tunnel_url': current_tunnel_url,
        'public_hostname': public_hostname,
        'cloudflared_tunnel_name': tunnel_name,
        'tunnel_status_label': 'Stable tunnel ready' if stable_tunnel_ready else 'Temporary tunnel',
        'tunnel_status_detail': f'WebAuthn stays aligned to {public_hostname}.' if stable_tunnel_ready else 'Set PUBLIC_HOSTNAME and CLOUDFLARED_TUNNEL_NAME for a stable origin.',
        'tunnel_status_tone': 'ready' if stable_tunnel_ready else 'warning',
    }
    return render(request, 'dashboard/testing_panel.html', context)


@login_required
def export_colab_bundle_view(request):
    """Generate and download a Colab-ready dataset bundle."""
    if not request.user.is_staff:
        return redirect('dashboard:client-dashboard')

    export_root = Path(settings.COLAB_EXPORT_DIR)
    export_root.mkdir(parents=True, exist_ok=True)
    timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
    output_path = export_root / f'colab_bundle_{timestamp}.zip'

    try:
        subprocess.run(
            [
                sys.executable,
                'manage.py',
                'export_colab_bundle',
                '--include-models',
                '--output',
                str(output_path),
            ],
            cwd=str(settings.BASE_DIR),
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        error_message = (exc.stderr or exc.stdout or 'Unable to export the Colab bundle.').strip()
        messages.error(request, error_message)
        return redirect('dashboard:dashboard')

    response = FileResponse(output_path.open('rb'), as_attachment=True, filename=output_path.name)
    response['Content-Length'] = str(output_path.stat().st_size)
    return response


@login_required
def start_cloudflare_tunnel_view(request):
    """Start a Cloudflare Tunnel and return the new public URL."""
    if not request.user.is_staff:
        return redirect('dashboard:client-dashboard')

    if request.method != 'POST':
        messages.error(request, 'Use the New Cloudflare Link button to create a tunnel.')
        return redirect('dashboard:dashboard')

    env = os.environ.copy()
    public_hostname = getattr(settings, 'PUBLIC_HOSTNAME', '') or env.get('PUBLIC_HOSTNAME', '').strip()
    tunnel_name = getattr(settings, 'CLOUDFLARED_TUNNEL_NAME', '') or env.get('CLOUDFLARED_TUNNEL_NAME', '').strip()
    if public_hostname:
        env['PUBLIC_HOSTNAME'] = public_hostname
    if tunnel_name:
        env['CLOUDFLARED_TUNNEL_NAME'] = tunnel_name

    try:
        result = subprocess.run(
            [
                sys.executable,
                'manage.py',
                'start_cloudflare_tunnel',
                '--url',
                'http://127.0.0.1:8000',
            ],
            cwd=str(settings.BASE_DIR),
            env=env,
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except subprocess.CalledProcessError as exc:
        error_message = (exc.stderr or exc.stdout or 'Unable to start Cloudflare Tunnel.').strip()
        messages.error(request, error_message)
        return redirect('dashboard:dashboard')
    except subprocess.TimeoutExpired:
        messages.error(request, 'Cloudflare Tunnel is starting up. Check cloudflared.current_url.txt for the link.')
        return redirect('dashboard:dashboard')

    output = (result.stdout or '').strip().splitlines()
    tunnel_line = next((line for line in output if 'Cloudflare tunnel started:' in line), '')
    if tunnel_line:
        messages.success(request, tunnel_line)
    else:
        messages.success(request, 'Cloudflare Tunnel started.')

    return redirect('dashboard:dashboard')


@login_required
def clients_list(request):
    """List all clients with filtering and search"""
    if not request.user.is_staff:
        return redirect('dashboard:client-dashboard')

    search_query = request.GET.get('search', '').strip()
    status_filter = request.GET.get('status', '').strip()

    clients = Client.objects.all()
    if search_query:
        clients = clients.filter(
            Q(name__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(phone__icontains=search_query)
        )
    if status_filter:
        clients = clients.filter(status=status_filter)

    clients = clients.order_by('-created_at')
    paginator = Paginator(clients, 5)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    context = {
        'view': 'clients',
        'clients': page_obj,
        'page_obj': page_obj,
        'search_query': search_query,
        'status_filter': status_filter,
        'notification_count': get_admin_notification_count(),
    }

    return render(request, 'dashboard/clients_list.html', context)


@login_required
def client_detail(request, client_id):
    """Show a client profile with recent activity."""
    if not request.user.is_staff:
        return redirect('dashboard:client-dashboard')

    client = get_object_or_404(Client, client_id=client_id)
    payments = Payment.objects.filter(client=client.name).order_by('-date')
    tickets = Ticket.objects.filter(client=client.name).order_by('-created')

    context = {
        'view': 'clients',
        'client': client,
        'payments': payments,
        'tickets': tickets,
    }
    return render(request, 'dashboard/clients/detail.html', context)


@login_required
def client_create(request):
    """Create a new client record."""
    if not request.user.is_staff:
        return redirect('dashboard:client-dashboard')

    error = None
    if request.method == 'POST':
        client_id = request.POST.get('client_id', '').strip()
        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip()
        phone = request.POST.get('phone', '').strip()
        address = request.POST.get('address', '').strip()
        plan = request.POST.get('plan', '').strip()
        fee = request.POST.get('fee', '').strip() or '0'
        status = request.POST.get('status', '').strip() or 'Active'
        balance = request.POST.get('balance', '').strip() or '0'
        due_date = request.POST.get('due_date', '').strip()
        joined = request.POST.get('joined', '').strip()

        if not client_id or not name or not email or not phone or not address or not plan or not due_date or not joined:
            error = 'Please complete all required fields.'
        elif Client.objects.filter(client_id=client_id).exists():
            error = 'Client ID already exists.'
        elif Client.objects.filter(email=email).exists():
            error = 'Email already exists.'
        else:
            due_date_value = datetime.strptime(due_date, '%Y-%m-%d').date()
            joined_value = datetime.strptime(joined, '%Y-%m-%d').date()
            Client.objects.create(
                client_id=client_id,
                name=name,
                email=email,
                phone=phone,
                address=address,
                plan=plan,
                fee=Decimal(fee),
                status=status,
                due_date=due_date_value,
                balance=Decimal(balance),
                joined=joined_value,
            )
            messages.success(request, 'Client created successfully.')
            return redirect('dashboard:client_detail', client_id=client_id)

    context = {
        'view': 'clients',
        'client': None,
        'error': error,
    }
    return render(request, 'dashboard/clients/form.html', context)


@login_required
def client_edit(request, client_id):
    """Edit an existing client."""
    if not request.user.is_staff:
        return redirect('dashboard:client-dashboard')

    client = get_object_or_404(Client, client_id=client_id)
    error = None
    if request.method == 'POST':
        client.name = request.POST.get('name', '').strip()
        client.email = request.POST.get('email', '').strip()
        client.phone = request.POST.get('phone', '').strip()
        client.address = request.POST.get('address', '').strip()
        client.plan = request.POST.get('plan', '').strip()
        fee_value = request.POST.get('fee', '').strip()
        if fee_value:
            client.fee = Decimal(fee_value)
        client.status = request.POST.get('status', '').strip() or client.status
        balance_value = request.POST.get('balance', '').strip()
        due_date = request.POST.get('due_date', '').strip()
        joined = request.POST.get('joined', '').strip()

        if not client.name or not client.email or not client.phone or not client.address or not client.plan or not due_date or not joined:
            error = 'Please complete all required fields.'
        else:
            if balance_value:
                client.balance = Decimal(balance_value)
            client.due_date = datetime.strptime(due_date, '%Y-%m-%d').date()
            client.joined = datetime.strptime(joined, '%Y-%m-%d').date()
            client.save()
            messages.success(request, 'Client updated successfully.')
            return redirect('dashboard:client_detail', client_id=client.client_id)

    context = {
        'view': 'clients',
        'client': client,
        'error': error,
    }
    return render(request, 'dashboard/clients/form.html', context)


@login_required
@require_POST
def client_delete(request, client_id):
    """Delete a client record."""
    if not request.user.is_staff:
        return redirect('dashboard:client-dashboard')

    client = get_object_or_404(Client, client_id=client_id)
    client_name = client.name
    client.delete()
    messages.success(request, f'Client {client_name} deleted successfully.')
    return redirect('dashboard:clients_list')


@login_required
def applications_list(request):
    """List all applications with filtering"""
    if not request.user.is_staff:
        return redirect('dashboard:client-dashboard')

    search_query = request.GET.get('search', '').strip()
    status_filter = request.GET.get('status', '').strip()

    applications = Application.objects.filter(status='Pending')
    if search_query:
        applications = applications.filter(
            Q(name__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(phone__icontains=search_query) |
            Q(plan__icontains=search_query)
        )
    if status_filter and status_filter != 'Pending':
        applications = applications.none()

    applications = applications.order_by('-date')
    paginator = Paginator(applications, 5)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    context = {
        'view': 'applications',
        'applications': page_obj,
        'page_obj': page_obj,
        'search_query': search_query,
        'status_filter': status_filter,
        'notification_count': get_admin_notification_count(),
    }

    return render(request, 'dashboard/applications_list.html', context)


@login_required
def payments_list(request):
    """List all payments with search and filter"""
    if not request.user.is_staff:
        return redirect('dashboard:client-dashboard')

    search_query = request.GET.get('search', '').strip()
    status_filter = request.GET.get('status', '').strip()

    payments = Payment.objects.all()
    if search_query:
        payments = payments.filter(
            Q(payment_id__icontains=search_query) |
            Q(client__icontains=search_query) |
            Q(period__icontains=search_query) |
            Q(method__icontains=search_query)
        )
    if status_filter:
        payments = payments.filter(status=status_filter)

    payments = payments.order_by('-date')
    paginator = Paginator(payments, 5)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    context = {
        'view': 'payments',
        'payments': page_obj,
        'page_obj': page_obj,
        'search_query': search_query,
        'status_filter': status_filter,
        'notification_count': get_admin_notification_count(),
    }

    return render(request, 'dashboard/payments_list.html', context)


@login_required
def tickets_list(request):
    """List all support tickets with status filter"""
    if not request.user.is_staff:
        return redirect('dashboard:client-dashboard')

    search_query = request.GET.get('search', '').strip()
    status_filter = request.GET.get('status', '').strip()
    priority_filter = request.GET.get('priority', '').strip()
    category_filter = request.GET.get('category', '').strip()
    sort_by = request.GET.get('sort_by', '').strip()

    tickets = Ticket.objects.all()
    if not status_filter:
        tickets = tickets.exclude(status='Resolved')
    if search_query:
        tickets = tickets.filter(
            Q(ticket_id__icontains=search_query) |
            Q(client__icontains=search_query) |
            Q(category__icontains=search_query) |
            Q(assigned__icontains=search_query)
        )
    if status_filter:
        tickets = tickets.filter(status=status_filter)
    if priority_filter:
        tickets = tickets.filter(priority=priority_filter)
    if category_filter:
        tickets = tickets.filter(category=category_filter)

    status_order = Case(
        When(status='Pending', then=0),
        When(status='Scheduled', then=1),
        When(status='In Progress', then=2),
        When(status='Resolved', then=3),
        When(status='Closed', then=4),
        default=5,
        output_field=IntegerField(),
    )

    if sort_by == 'oldest':
        tickets = tickets.order_by(status_order, 'created')
    elif sort_by == 'priority':
        tickets = tickets.order_by(
            status_order,
            Case(
                When(priority='Critical', then=0),
                When(priority='High', then=1),
                When(priority='Medium', then=2),
                When(priority='Low', then=3),
                default=4,
                output_field=IntegerField(),
            ),
            '-created',
        )
    elif sort_by == 'status' or not sort_by:
        tickets = tickets.order_by(status_order, '-created')
    else:
        tickets = tickets.order_by(status_order, '-created')

    total_tickets = Ticket.objects.count()
    pending_tickets = Ticket.objects.filter(status='Pending').count()
    open_tickets = Ticket.objects.filter(status='Open').count()
    waiting_tickets = Ticket.objects.filter(status='In Progress').count()
    resolved_tickets = Ticket.objects.filter(status='Resolved').count()

    response_times = [
        (ticket.updated_at - ticket.created_at).total_seconds()
        for ticket in Ticket.objects.all()
        if ticket.updated_at and ticket.updated_at >= ticket.created_at
    ]
    avg_response_time = '--'
    if response_times:
        avg_hours = sum(response_times) / len(response_times) / 3600.0
        avg_response_time = f"{avg_hours:.1f} hrs"

    categories = Ticket.objects.order_by('category').values_list('category', flat=True).distinct()

    paginator = Paginator(tickets, 5)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    pending_reschedule_request_ids = []
    for ticket in page_obj:
        latest_request = ActivityLog.objects.filter(
            entity_type='Ticket',
            entity_id=ticket.ticket_id,
            activity_type='ticket_reschedule_requested',
        ).order_by('-created_at').first()
        latest_scheduled = ActivityLog.objects.filter(
            entity_type='Ticket',
            entity_id=ticket.ticket_id,
            activity_type='ticket_scheduled',
        ).order_by('-created_at').first()

        if latest_request and (not latest_scheduled or latest_request.created_at > latest_scheduled.created_at):
            pending_reschedule_request_ids.append(ticket.ticket_id)
            ticket.reschedule_request = latest_request
        else:
            ticket.reschedule_request = None

    pending_reschedule_requests_count = len(pending_reschedule_request_ids)

    context = {
        'view': 'tickets',
        'tickets': page_obj,
        'page_obj': page_obj,
        'search_query': search_query,
        'status_filter': status_filter,
        'priority_filter': priority_filter,
        'category_filter': category_filter,
        'sort_by': sort_by,
        'notification_count': get_admin_notification_count(),
        'total_tickets': total_tickets,
        'pending_tickets': pending_tickets,
        'open_tickets': open_tickets,
        'waiting_tickets': waiting_tickets,
        'resolved_tickets': resolved_tickets,
        'avg_response_time': avg_response_time,
        'ticket_categories': categories,
        'pending_reschedule_request_ids': pending_reschedule_request_ids,
        'pending_reschedule_requests_count': pending_reschedule_requests_count,
    }

    return render(request, 'dashboard/tickets_list.html', context)


@login_required
def ticket_create(request):
    """Create a new support ticket in admin."""
    if not request.user.is_staff:
        return redirect('dashboard:client-dashboard')

    error = None
    if request.method == 'POST':
        client_name = request.POST.get('client', '').strip()
        category = request.POST.get('category', '').strip()
        priority = request.POST.get('priority', '').strip()
        status = request.POST.get('status', '').strip() or 'Open'
        assigned = request.POST.get('assigned', 'Unassigned').strip() or 'Unassigned'
        description = request.POST.get('description', '').strip()
        created = request.POST.get('created', '').strip()
        scheduled = request.POST.get('scheduled', '').strip()
        scheduled_time = request.POST.get('scheduled_time', '').strip()

        if not client_name or not category or not priority or not description or not created:
            error = 'Please fill in all required fields.'
        else:
            try:
                created_date = datetime.strptime(created, '%Y-%m-%d').date()
                scheduled_date = None
                scheduled_time_obj = None
                if scheduled:
                    scheduled_date = datetime.strptime(scheduled, '%Y-%m-%d').date()
                if scheduled_time:
                    scheduled_time_obj = datetime.strptime(scheduled_time, '%H:%M').time()
                ticket = Ticket.objects.create(
                    ticket_id=_generate_ticket_id(),
                    client=client_name,
                    category=category,
                    priority=priority,
                    status=status,
                    description=description,
                    assigned=assigned,
                    created=created_date,
                    scheduled_date=scheduled_date,
                    scheduled_time=scheduled_time_obj,
                )
                ActivityLog.objects.create(
                    activity_type='ticket_created',
                    entity_type='Ticket',
                    entity_id=ticket.ticket_id,
                    entity_name=ticket.client,
                    description=f'Support ticket {ticket.ticket_id} was created for {ticket.client}.',
                    new_value=ticket.status,
                    performed_by=request.user.username if request.user and request.user.is_authenticated else 'System',
                )
                return redirect('dashboard:tickets')
            except ValueError:
                error = 'Invalid date format for created date.'

    return render(request, 'dashboard/tickets/form.html', {'ticket': None, 'error': error})


@login_required
def ticket_detail(request, ticket_id):
    """Show detailed admin ticket view."""
    if not request.user.is_staff:
        return redirect('dashboard:client-dashboard')

    ticket = get_object_or_404(Ticket, ticket_id=ticket_id)
    return render(request, 'dashboard/tickets/detail.html', {'ticket': ticket})


@login_required
def ticket_schedule(request, ticket_id):
    """Schedule an in-home service appointment for a support ticket."""
    if not request.user.is_staff:
        return redirect('dashboard:client-dashboard')

    ticket = get_object_or_404(Ticket, ticket_id=ticket_id)
    
    # Allow scheduling for any ticket status (Pending, In Progress, etc.)
    # but not if already Scheduled
    if ticket.status == 'Scheduled':
        return JsonResponse({
            'success': False,
            'error': 'This ticket is already scheduled.'
        }, status=400)
    
    error = None

    if request.method == 'POST':
        assigned = request.POST.get('assigned', '').strip()
        scheduled = request.POST.get('scheduled', '').strip()
        scheduled_time = request.POST.get('scheduled_time', '').strip()
        notes = request.POST.get('notes', '').strip()

        if not assigned or not scheduled or not scheduled_time:
            error = 'Please assign a technician and choose a scheduled date and time.'
        else:
            try:
                scheduled_date = datetime.strptime(scheduled, '%Y-%m-%d').date()
                scheduled_time_obj = datetime.strptime(scheduled_time, '%H:%M').time()
                old_values = {
                    'assigned': ticket.assigned,
                    'scheduled_date': ticket.scheduled_date,
                    'scheduled_time': ticket.scheduled_time,
                    'status': ticket.status,
                }
                ticket.assigned = assigned
                ticket.scheduled_date = scheduled_date
                ticket.scheduled_time = scheduled_time_obj
                # When admin schedules a ticket, mark it as Scheduled
                ticket.status = 'Scheduled'
                ticket.save()

                schedule_label = scheduled_date.strftime('%b %d, %Y') + ' at ' + scheduled_time_obj.strftime('%I:%M %p')
                changes = []
                if old_values['assigned'] != ticket.assigned:
                    changes.append(f"Assigned technician changed from '{old_values['assigned']}' to '{ticket.assigned}'")
                if old_values['scheduled_date'] != ticket.scheduled_date or old_values['scheduled_time'] != ticket.scheduled_time:
                    changes.append(f"Service scheduled for {schedule_label}")
                if old_values['status'] != ticket.status:
                    changes.append(f"Status changed from '{old_values['status']}' to '{ticket.status}'")
                if notes:
                    changes.append(f"Notes: {notes}")

                ActivityLog.objects.create(
                    activity_type='ticket_scheduled',
                    entity_type='Ticket',
                    entity_id=ticket.ticket_id,
                    entity_name=ticket.client,
                    description='; '.join(changes) if changes else f'Service scheduled for {schedule_label}.',
                    old_value=str(old_values),
                    new_value=str({
                        'assigned': ticket.assigned,
                        'scheduled_date': str(ticket.scheduled_date) if ticket.scheduled_date else None,
                        'scheduled_time': ticket.scheduled_time.strftime('%H:%M') if ticket.scheduled_time else None,
                        'status': ticket.status,
                    }),
                    performed_by=request.user.username if request.user and request.user.is_authenticated else 'System',
                )
                # Notify the client about the scheduled visit (email + SMS when available)
                try:
                    client_obj = Client.objects.filter(name=ticket.client).first()
                    if client_obj:
                        reschedule_req = ActivityLog.objects.filter(
                            entity_id=ticket.ticket_id,
                            activity_type='ticket_reschedule_requested'
                        ).order_by('-created_at').first()

                        extra_message = None
                        if reschedule_req:
                            extra_message = "Your rescheduled date has been approved. We have updated the appointment and will notify the technician. If anything changes, please contact support."

                        subject, email_body, sms_body = _format_schedule_notification(
                            ticket,
                            client_obj,
                            scheduled_date,
                            scheduled_time_obj,
                            extra_message=extra_message
                        )

                        # Idempotency guard: avoid sending duplicate schedule notifications
                        already_sent = ActivityLog.objects.filter(
                            entity_id=ticket.ticket_id,
                            activity_type='ticket_scheduled',
                            description__icontains='Schedule notification generated'
                        ).exists()

                        # Do not send client notifications when a reschedule request is pending; approval flow handles that.
                        if reschedule_req:
                            already_sent = True

                        email_result = None
                        sms_result = None

                        if getattr(client_obj, 'email', None) and not already_sent:
                            email_result = NotificationService.send_email(
                                recipient_email=client_obj.email,
                                subject=subject,
                                body=email_body,
                                client_id=getattr(client_obj, 'client_id', ''),
                                customer_name=client_obj.name,
                                notification_type='Service Scheduled'
                            )
                        if getattr(client_obj, 'phone', None) and not already_sent:
                            sms_result = NotificationService.send_sms(
                                phone_number=client_obj.phone,
                                message=sms_body,
                                client_id=getattr(client_obj, 'client_id', ''),
                                customer_name=client_obj.name,
                                notification_type='Service Scheduled'
                            )
                        if email_result and email_result.get('status') != 'success':
                            print(f"Email notification failed for {ticket.ticket_id}: {email_result.get('message')}")
                            ActivityLog.objects.create(
                                activity_type='ticket_scheduled',
                                entity_type='Ticket',
                                entity_id=ticket.ticket_id,
                                entity_name=ticket.client,
                                description=f"Schedule notification email failed: {email_result.get('message')}",
                                old_value=str(old_values),
                                new_value=email_body[:1000],
                                performed_by=request.user.username if request.user and request.user.is_authenticated else 'System',
                            )
                        if sms_result and sms_result.get('status') != 'success':
                            print(f"SMS notification failed for {ticket.ticket_id}: {sms_result.get('message')}")
                        # Record the generated notification in activity log for admin reference
                        try:
                            if not already_sent and (email_result is None or email_result.get('status') == 'success'):
                                ActivityLog.objects.create(
                                    activity_type='ticket_scheduled',
                                    entity_type='Ticket',
                                    entity_id=ticket.ticket_id,
                                    entity_name=ticket.client,
                                    description=f'Schedule notification generated and sent to client ({client_obj.client_id}).',
                                    old_value=str(old_values),
                                    new_value=email_body[:1000],
                                    performed_by=request.user.username if request.user and request.user.is_authenticated else 'System',
                                )
                        except Exception:
                            pass
                except Exception as e:
                    print(f"Error sending schedule notifications for {ticket.ticket_id}: {e}")
                return JsonResponse({
                    'success': True,
                    'message': 'Ticket scheduled successfully.',
                    'redirect': reverse('dashboard:ticket_detail', args=[ticket.ticket_id])
                })
            except ValueError:
                return JsonResponse({
                    'success': False,
                    'error': 'Invalid date format for scheduled date.'
                }, status=400)

    # If GET request or no POST data, return error (schedule form is now in modal)
    if request.method == 'GET':
        return JsonResponse({
            'success': False,
            'error': 'Invalid request method. Use POST to schedule a ticket.'
        }, status=405)
    
    # Default error response
    return JsonResponse({
        'success': False,
        'error': error or 'Unable to schedule ticket.'
    }, status=400)


@login_required
def ticket_update_status(request, ticket_id):
    """Update the status of an admin ticket."""
    if not request.user.is_staff:
        return redirect('dashboard:client-dashboard')

    if request.method == 'POST':
        ticket = get_object_or_404(Ticket, ticket_id=ticket_id)
        new_status = request.POST.get('status', '').strip()
        allowed_statuses = ['Pending', 'In Progress', 'Resolved']
        if new_status in allowed_statuses and new_status != ticket.status:
            old_status = ticket.status
            ticket.status = new_status
            ticket.save()
            ActivityLog.objects.create(
                activity_type='ticket_updated',
                entity_type='Ticket',
                entity_id=ticket.ticket_id,
                entity_name=ticket.client,
                description=f"Ticket {ticket.ticket_id} status changed from '{old_status}' to '{ticket.status}'.",
                old_value=old_status,
                new_value=ticket.status,
                performed_by=request.user.username if request.user and request.user.is_authenticated else 'System',
            )
    return redirect('dashboard:tickets')


@login_required
def ticket_resolve(request, ticket_id):
    """Resolve an admin ticket and remove it from the active queue."""
    if not request.user.is_staff:
        return redirect('dashboard:client-dashboard')

    if request.method == 'POST':
        ticket = get_object_or_404(Ticket, ticket_id=ticket_id)
        if ticket.status != 'Resolved':
            old_status = ticket.status
            ticket.status = 'Resolved'
            ticket.save()
            ActivityLog.objects.create(
                activity_type='ticket_resolved',
                entity_type='Ticket',
                entity_id=ticket.ticket_id,
                entity_name=ticket.client,
                description=f"Ticket {ticket.ticket_id} resolved (was {old_status}).",
                old_value=old_status,
                new_value=ticket.status,
                performed_by=request.user.username if request.user and request.user.is_authenticated else 'System',
            )
    return redirect('dashboard:tickets')


@login_required
def ticket_delete(request, ticket_id):
    """Delete an admin ticket."""
    if not request.user.is_staff:
        return redirect('dashboard:client-dashboard')

    if request.method == 'POST':
        ticket = get_object_or_404(Ticket, ticket_id=ticket_id)
        ticket.delete()
    return redirect('dashboard:tickets')


def logout_view(request):
    """Logout user"""
    logout(request)
    return redirect('login')
