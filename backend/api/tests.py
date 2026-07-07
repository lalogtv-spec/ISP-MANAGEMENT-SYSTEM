from django.test import TestCase, Client as TestClient
from api.models import Client, Application, ApplicationDecision, Ticket, Payment
from rest_framework.test import APITestCase
from rest_framework import status


class ClientAPITestCase(APITestCase):
    def setUp(self):
        self.client = TestClient()
        self.client_data = Client.objects.create(
            client_id='C001',
            name='Test Client',
            address='123 Test St',
            phone='09123456789',
            email='test@email.com',
            plan='Standard 50Mbps',
            fee=1299,
            status='Active',
            due_date='2026-06-25',
            balance=0,
            joined='2024-01-15'
        )

    def test_get_clients_list(self):
        response = self.client.get('/api/clients/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_get_client_detail(self):
        response = self.client.get(f'/api/clients/{self.client_data.client_id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Test Client')

    def test_create_client(self):
        data = {
            'client_id': 'C002',
            'name': 'New Client',
            'address': '456 Test Ave',
            'phone': '09198765432',
            'email': 'new@email.com',
            'plan': 'Premium 100Mbps',
            'fee': 1899,
            'status': 'Active',
            'due_date': '2026-06-25',
            'balance': 0,
            'joined': '2024-01-15'
        }
        response = self.client.post('/api/clients/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_filter_clients_by_status(self):
        response = self.client.get('/api/clients/?status=Active')
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class ApplicationAPITestCase(APITestCase):
    def setUp(self):
        self.app_data = Application.objects.create(
            app_id='APP-001',
            name='Test Applicant',
            phone='09123456789',
            email='applicant@email.com',
            address='123 Test St',
            plan='Standard 50Mbps',
            status='Pending',
            date='2026-06-12'
        )

    def test_get_applications_list(self):
        response = self.client.get('/api/applications/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_get_pending_applications(self):
        response = self.client.get('/api/applications/pending/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_approve_application_creates_client_and_removes_application(self):
        response = self.client.patch(
            '/api/applications/APP-001/',
            data='{"status":"Approved"}',
            content_type='application/json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(Application.objects.filter(app_id='APP-001').exists())
        self.assertTrue(Client.objects.filter(email='applicant@email.com').exists())

    def test_decline_application_removes_application(self):
        response = self.client.patch(
            '/api/applications/APP-001/',
            data='{"status":"Declined","reason":"Service area is unavailable"}',
            content_type='application/json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(Application.objects.filter(app_id='APP-001').exists())
        self.assertFalse(Client.objects.filter(email='applicant@email.com').exists())
        self.assertTrue(ApplicationDecision.objects.filter(app_id='APP-001', reason='Service area is unavailable').exists())


class TicketAPITestCase(APITestCase):
    def setUp(self):
        self.ticket_data = Ticket.objects.create(
            ticket_id='TKT-2026-001',
            client='Maria Santos',
            category='Slow Speed',
            priority='High',
            status='In Progress',
            description='Test issue',
            assigned='Unassigned',
            created='2026-06-13'
        )

    def test_get_tickets_list(self):
        response = self.client.get('/api/tickets/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_get_critical_tickets(self):
        response = self.client.get('/api/tickets/critical/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class PaymentAPITestCase(APITestCase):
    def setUp(self):
        self.payment_data = Payment.objects.create(
            payment_id='PAY-001',
            client='Maria Santos',
            date='2026-06-15',
            amount=1899,
            period='June 2026',
            method='GCash',
            status='Verified'
        )

    def test_get_payments_list(self):
        response = self.client.get('/api/payments/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_get_pending_payments(self):
        response = self.client.get('/api/payments/pending/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
