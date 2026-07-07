from datetime import date, timedelta
from decimal import Decimal
import base64
import hashlib

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, utils as asym_utils
from django.contrib.auth import get_user_model
from django.core import signing
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
import json

from api.models import Client, Payment, OverdueNotification, Ticket
from api.notification_service import NotificationService
from dashboard.client_views import _calculate_service_end_date
from security.encryption import EncryptionService
from api.models import ActivityLog
from security.models import AuditLog, BiometricData
from security.webauthn import verify_webauthn_assertion


class LoginPageViewTests(TestCase):
    def test_login_page_renders_face_and_fingerprint_login(self):
        response = self.client.get(reverse('login'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Face Login')
        self.assertContains(response, 'Fingerprint Login')
        self.assertContains(response, 'Use your phone or device face or fingerprint biometrics for quick sign in.')
        self.assertContains(response, 'Ready for face or fingerprint login.')
        self.assertNotContains(response, 'Biometric Face Verification')


class FingerprintLoginViewTests(TestCase):
    def test_begin_fingerprint_login_stores_origin_and_rp_id_for_verification(self):
        response = self.client.get(
            reverse('dashboard:fingerprint-login-begin'),
            {'origin': 'https://example.test', 'rp_id': 'example.test'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.session['direct_fingerprint_login_origin'], 'https://example.test')
        self.assertEqual(self.client.session['direct_fingerprint_login_rp_id'], 'example.test')

    def test_begin_fingerprint_login_returns_registered_passkey_credentials(self):
        user = get_user_model().objects.create_user(
            username='fingerprintuser',
            password='secret123',
            email='fingerprint@example.com',
        )
        BiometricData.objects.create(
            user=user,
            biometric_type='mobile_passkey',
            template_data=EncryptionService.encrypt_data(json.dumps({
                'credential_id': 'abc123',
                'public_key': {'x': 'x', 'y': 'y'},
            })),
            template_hash='hash',
            is_active=True,
        )

        response = self.client.get(
            reverse('dashboard:fingerprint-login-begin'),
            {'origin': 'https://example.test', 'rp_id': 'example.test'},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn('allowCredentials', payload['options'])
        self.assertEqual(payload['options']['allowCredentials'][0]['id'], 'abc123')

    def test_begin_fingerprint_login_accepts_plain_json_credentials(self):
        user = get_user_model().objects.create_user(
            username='plainjsonuser',
            password='secret123',
            email='plainjson@example.com',
        )
        BiometricData.objects.create(
            user=user,
            biometric_type='mobile_passkey',
            template_data=json.dumps({
                'credential_id': 'plain-cred',
                'public_key': {'x': 'x', 'y': 'y'},
            }),
            template_hash='hash-plain',
            is_active=True,
        )

        response = self.client.get(
            reverse('dashboard:fingerprint-login-begin'),
            {'origin': 'https://example.test', 'rp_id': 'example.test'},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['options']['allowCredentials'][0]['id'], 'plain-cred')

    def test_begin_fingerprint_login_uses_forwarded_host_for_rp_id(self):
        response = self.client.get(
            reverse('dashboard:fingerprint-login-begin'),
            {'origin': 'https://app.example.test', 'rp_id': 'app.example.test'},
            HTTP_HOST='internal.local',
            HTTP_X_FORWARDED_HOST='app.example.test',
            HTTP_X_FORWARDED_PROTO='https',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.session['direct_fingerprint_login_origin'], 'https://app.example.test')
        self.assertEqual(self.client.session['direct_fingerprint_login_rp_id'], 'app.example.test')

    def test_complete_fingerprint_login_accepts_authenticators_without_uv_flag(self):
        user = get_user_model().objects.create_user(
            username='uvlessuser',
            password='secret123',
            email='uvless@example.com',
        )
        private_key = ec.generate_private_key(ec.SECP256R1())
        public_numbers = private_key.public_key().public_numbers()
        public_key_payload = {
            'kty': 2,
            'alg': -7,
            'crv': 1,
            'x': 'x',
            'y': 'y',
        }
        credential_id = 'uvless-cred'
        BiometricData.objects.create(
            user=user,
            biometric_type='mobile_passkey',
            template_data=json.dumps({
                'credential_id': credential_id,
                'public_key': public_key_payload,
                'sign_count': 0,
                'rp_id': 'example.test',
                'origin': 'https://example.test',
            }),
            template_hash='hash-uvless',
            is_active=True,
        )

        client = self.client
        begin_response = client.get(
            reverse('dashboard:fingerprint-login-begin'),
            {'origin': 'https://example.test', 'rp_id': 'example.test'},
        )
        self.assertEqual(begin_response.status_code, 200)
        challenge = begin_response.json()['options']['challenge']

        client_data = {
            'type': 'webauthn.get',
            'challenge': challenge,
            'origin': 'https://example.test',
        }
        client_data_json = json.dumps(client_data).encode('utf-8')
        client_hash = hashlib.sha256(client_data_json).digest()
        rp_hash = hashlib.sha256(b'example.test').digest()
        authenticator_data = rp_hash + bytes([0x01]) + (1).to_bytes(4, 'big')
        signed_data = authenticator_data + client_hash
        signature_der = private_key.sign(signed_data, ec.ECDSA(hashes.SHA256()))
        r, s = asym_utils.decode_dss_signature(signature_der)
        raw_signature = r.to_bytes(32, 'big') + s.to_bytes(32, 'big')

        payload = {
            'credential': {
                'id': credential_id,
                'rawId': credential_id,
                'type': 'public-key',
                'response': {
                    'clientDataJSON': base64.b64encode(client_data_json).decode('ascii'),
                    'authenticatorData': base64.b64encode(authenticator_data).decode('ascii'),
                    'signature': base64.b64encode(raw_signature).decode('ascii'),
                    'userHandle': '',
                },
            }
        }
        finish_response = client.post(
            reverse('dashboard:fingerprint-login-finish'),
            json.dumps(payload),
            content_type='application/json',
        )

        self.assertEqual(finish_response.status_code, 200)
        self.assertTrue(finish_response.json()['success'])

    def test_begin_fingerprint_login_skips_credentials_from_other_rp_ids(self):
        user = get_user_model().objects.create_user(
            username='otherdomainuser',
            password='secret123',
            email='otherdomain@example.com',
        )
        BiometricData.objects.create(
            user=user,
            biometric_type='mobile_passkey',
            template_data=json.dumps({
                'credential_id': 'other-domain-cred',
                'public_key': {'x': 'x', 'y': 'y'},
                'rp_id': 'different.example.test',
            }),
            template_hash='hash-other-rp',
            is_active=True,
        )

        response = self.client.get(
            reverse('dashboard:fingerprint-login-begin'),
            {'origin': 'https://example.test', 'rp_id': 'example.test'},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['options']['allowCredentials'], [])


class NotificationDashboardViewTests(TestCase):
    def test_admin_notification_dashboard_shows_ticket_id_for_open_tickets(self):
        user = get_user_model().objects.create_user(
            username='adminnotify',
            password='secret123',
            is_staff=True,
            is_superuser=True,
        )
        Ticket.objects.create(
            ticket_id='TKT1001',
            client='Juan Dela Cruz',
            category='Billing',
            priority='High',
            status='Open',
            description='Connection issue after payment.',
            created=date.today(),
        )

        self.client.force_login(user)
        response = self.client.get(reverse('dashboard:notification-dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'TKT1001')

    def test_admin_notification_dashboard_shows_reschedule_request_activity(self):
        user = get_user_model().objects.create_user(
            username='adminnotify2',
            password='secret123',
            is_staff=True,
            is_superuser=True,
        )
        ticket = Ticket.objects.create(
            ticket_id='TKT1002',
            client='Client Two',
            category='Installation',
            priority='Medium',
            status='Pending',
            description='Install new router.',
            created=date.today(),
        )
        ActivityLog.objects.create(
            activity_type='ticket_reschedule_requested',
            entity_type='Ticket',
            entity_id=ticket.ticket_id,
            entity_name=ticket.client,
            description='Client requested reschedule to Jun 30, 2026 at 09:30 AM. Reason: Prefer morning',
            performed_by='clientuser2',
        )

        self.client.force_login(user)
        response = self.client.get(reverse('dashboard:notification-dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Reschedule Request')
        self.assertContains(response, 'Prefer morning')


class FaceLoginViewTests(TestCase):
    def test_begin_face_login_stores_origin_and_rp_id_for_verification(self):
        response = self.client.get(
            reverse('dashboard:face-login-begin'),
            {'origin': 'https://example.test', 'rp_id': 'example.test'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.session['direct_face_login_origin'], 'https://example.test')
        self.assertEqual(self.client.session['direct_face_login_rp_id'], 'example.test')

    def test_begin_face_login_returns_registered_passkey_credentials(self):
        user = get_user_model().objects.create_user(
            username='faceuser',
            password='secret123',
            email='face@example.com',
        )
        BiometricData.objects.create(
            user=user,
            biometric_type='mobile_passkey',
            template_data=EncryptionService.encrypt_data(json.dumps({
                'credential_id': 'abc123',
                'public_key': {'x': 'x', 'y': 'y'},
            })),
            template_hash='hash',
            is_active=True,
        )

        response = self.client.get(
            reverse('dashboard:face-login-begin'),
            {'origin': 'https://example.test', 'rp_id': 'example.test'},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn('allowCredentials', payload['options'])
        self.assertEqual(payload['options']['allowCredentials'][0]['id'], 'abc123')


class WebAuthnSignatureTests(TestCase):
    def test_verify_webauthn_assertion_accepts_raw_concat_signature(self):
        private_key = ec.generate_private_key(ec.SECP256R1())
        authenticator_data = b'\x00' * 37
        client_data_json = b'{"type":"webauthn.get"}'
        signed_data = authenticator_data + hashlib.sha256(client_data_json).digest()
        signature_der = private_key.sign(signed_data, ec.ECDSA(hashes.SHA256()))
        r, s = asym_utils.decode_dss_signature(signature_der)
        raw_signature = r.to_bytes(32, 'big') + s.to_bytes(32, 'big')

        verify_webauthn_assertion(private_key.public_key(), authenticator_data, client_data_json, raw_signature)


class SecuritySettingsViewTests(TestCase):
    def test_security_settings_renders_phone_biometric_settings(self):
        user = get_user_model().objects.create_user(
            username='securityuser',
            password='secret123',
            email='security@example.com',
        )
        self.client.force_login(user)

        response = self.client.get(reverse('dashboard:security-settings'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Fingerprint Registration')
        self.assertContains(response, 'Use the phone fingerprint prompt first.')
        self.assertContains(response, 'Face Enrollment')
        self.assertContains(response, 'Capture your face for facial biometric sign-in and verification.')


class AuditLogViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='adminuser',
            password='secret123',
            is_staff=True,
            is_superuser=True,
        )

    def test_audit_log_view_shows_security_audit_entries(self):
        AuditLog.objects.create(
            user=self.user,
            action_type='login',
            description='User logged in successfully',
            ip_address='127.0.0.1',
            status='success',
        )

        self.client.force_login(self.user)
        response = self.client.get(reverse('dashboard:audit-log'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'User logged in successfully')
        self.assertContains(response, 'Login')

    def test_audit_log_view_shows_activity_log_entries(self):
        ActivityLog.objects.create(
            activity_type='payment_recorded',
            entity_type='Payment',
            entity_id='PAY123',
            entity_name='Test Client',
            description='Payment received for Test Client',
            amount=Decimal('1500.00'),
            performed_by='adminuser',
        )

        self.client.force_login(self.user)
        response = self.client.get(reverse('dashboard:audit-log'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Payment received for Test Client')
        self.assertContains(response, 'Payment Recorded')


class ClientPaymentsViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='clientuser',
            password='secret123',
            email='client@example.com',
        )
        self.client_obj = Client.objects.create(
            client_id='C001',
            name='Test Client',
            email=self.user.email,
            phone='09171234567',
            address='Test Address',
            plan='Basic',
            fee=Decimal('499.00'),
            status='Active',
            due_date=date(2026, 1, 15),
            balance=Decimal('0.00'),
            joined=date(2025, 1, 1),
        )

    def test_calculate_service_end_date_uses_verified_payment_coverage(self):
        Payment.objects.create(
            payment_id='PAY001',
            client=self.client_obj.name,
            date=date(2026, 1, 10),
            amount=Decimal('998.00'),
            period='Advance Month',
            method='GCash',
            status='Verified',
        )

        service_end_date = _calculate_service_end_date(self.client_obj)

        self.assertEqual(service_end_date, date(2026, 3, 10))

    def test_client_notifications_view_shows_overdue_alerts_for_overdue_clients(self):
        self.client_obj.due_date = date.today() - timedelta(days=10)
        self.client_obj.balance = Decimal('499.00')
        self.client_obj.save(update_fields=['due_date', 'balance'])

        self.client.force_login(self.user)
        response = self.client.get(reverse('dashboard:client-notifications'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Disconnection Warning')


class ClientRescheduleNotificationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='clientuser2',
            password='secret123',
            email='client2@example.com',
        )
        self.client_obj = Client.objects.create(
            client_id='C002',
            name='Client Two',
            email=self.user.email,
            phone='09171230000',
            address='Test Address 2',
            plan='Basic',
            fee=Decimal('499.00'),
            status='Active',
            due_date=date(2026, 1, 15),
            balance=Decimal('0.00'),
            joined=date(2025, 1, 1),
        )
        self.ticket = Ticket.objects.create(
            ticket_id='TKT2001',
            client=self.client_obj.name,
            category='Installation',
            priority='Low',
            status='Pending',
            description='Install new connection',
            created=date.today(),
        )

    def test_reschedule_sends_one_email_and_sms(self):
        self.client.force_login(self.user)
        url = reverse('dashboard:client-ticket-reschedule', args=[self.ticket.ticket_id])
        future = date.today() + timedelta(days=2)
        response = self.client.post(url, data={
            'scheduled': future.strftime('%Y-%m-%d'),
            'scheduled_time': '09:30',
            'reason': 'Prefer morning'
        })
        # After redirect, client should not receive notifications yet
        self.assertEqual(response.status_code, 302)
        # Ensure a reschedule request ActivityLog was created
        req = ActivityLog.objects.filter(entity_id=self.ticket.ticket_id, activity_type='ticket_reschedule_requested').first()
        self.assertIsNotNone(req)

    def test_reschedule_request_appears_in_client_notifications(self):
        self.client.force_login(self.user)
        url = reverse('dashboard:client-ticket-reschedule', args=[self.ticket.ticket_id])
        future = date.today() + timedelta(days=2)
        self.client.post(url, data={
            'scheduled': future.strftime('%Y-%m-%d'),
            'scheduled_time': '09:30',
            'reason': 'Prefer morning'
        })

        response = self.client.get(reverse('dashboard:client-notifications'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Ticket Reschedule Requested')
        self.assertContains(response, 'Prefer morning')

    def test_reschedule_idempotent_on_quick_repost(self):
        self.client.force_login(self.user)
        url = reverse('dashboard:client-ticket-reschedule', args=[self.ticket.ticket_id])
        future = date.today() + timedelta(days=3)
        # First post
        r1 = self.client.post(url, data={'scheduled': future.strftime('%Y-%m-%d'), 'scheduled_time': '10:00', 'reason': ''})
        self.assertEqual(r1.status_code, 302)
        # Second immediate post should not create duplicate logs
        r2 = self.client.post(url, data={'scheduled': future.strftime('%Y-%m-%d'), 'scheduled_time': '10:00', 'reason': ''})
        self.assertEqual(r2.status_code, 302)
        # Only one reschedule request activity should exist
        reqs = ActivityLog.objects.filter(entity_id=self.ticket.ticket_id, activity_type='ticket_reschedule_requested')
        self.assertEqual(reqs.count(), 1)

    def test_overdue_state_transition_creates_notification_record(self):
        self.client_obj.due_date = date.today() - timedelta(days=2)
        self.client_obj.balance = Decimal('499.00')
        self.client_obj.status = 'Active'
        self.client_obj.save(update_fields=['due_date', 'balance', 'status'])

        notification = NotificationService.ensure_overdue_notification(self.client_obj)

        self.assertIsNotNone(notification)
        self.assertEqual(notification.notification_type, 'Second Notice')
        self.assertEqual(self.client_obj.status, 'Overdue')
        self.assertTrue(OverdueNotification.objects.filter(client=self.client_obj.client_id).exists())

    def test_overdue_state_transition_creates_follow_up_notice_when_type_changes(self):
        self.client_obj.due_date = date.today() - timedelta(days=1)
        self.client_obj.balance = Decimal('499.00')
        self.client_obj.status = 'Active'
        self.client_obj.save(update_fields=['due_date', 'balance', 'status'])

        first_notification = NotificationService.ensure_overdue_notification(self.client_obj)
        self.assertIsNotNone(first_notification)
        self.assertEqual(first_notification.notification_type, 'First Notice')

        self.client_obj.due_date = date.today() - timedelta(days=2)
        self.client_obj.save(update_fields=['due_date'])

        second_notification = NotificationService.ensure_overdue_notification(self.client_obj)
        self.assertIsNotNone(second_notification)
        self.assertEqual(second_notification.notification_type, 'Second Notice')
        self.assertEqual(OverdueNotification.objects.filter(client=self.client_obj.client_id).count(), 2)
