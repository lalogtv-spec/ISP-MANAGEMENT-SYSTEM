import json
from django.core.management.base import BaseCommand
from api.models import Client, Application, Ticket, Payment
from datetime import datetime


class Command(BaseCommand):
    help = 'Load initial data for ISP Management System'

    def handle(self, *args, **options):
        # Clear existing data
        Client.objects.all().delete()
        Application.objects.all().delete()
        Ticket.objects.all().delete()
        Payment.objects.all().delete()

        # Create Clients
        clients_data = [
            {
                'client_id': 'C001',
                'name': 'Maria Santos',
                'address': '456 Rizal St, Brgy. Poblacion',
                'phone': '09171234567',
                'email': 'maria@email.com',
                'plan': 'Premium 100Mbps',
                'fee': 1899,
                'status': 'Active',
                'due_date': '2026-06-25',
                'balance': 0,
                'joined': '2024-01-15'
            },
            {
                'client_id': 'C002',
                'name': 'Juan dela Cruz',
                'address': '789 Mabini Ave, Brgy. San Jose',
                'phone': '09181234567',
                'email': 'juan@email.com',
                'plan': 'Standard 50Mbps',
                'fee': 1299,
                'status': 'Overdue',
                'due_date': '2026-06-05',
                'balance': 1299,
                'joined': '2024-03-22'
            },
            {
                'client_id': 'C003',
                'name': 'Ana Reyes',
                'address': '123 Bonifacio Blvd, Brgy. Sta. Cruz',
                'phone': '09191234567',
                'email': 'ana@email.com',
                'plan': 'Basic 25Mbps',
                'fee': 899,
                'status': 'Disconnected',
                'due_date': '2026-05-30',
                'balance': 1798,
                'joined': '2023-08-10'
            },
            {
                'client_id': 'C004',
                'name': 'Pedro Garcia',
                'address': '321 Luna St, Brgy. Bagong Silang',
                'phone': '09201234567',
                'email': 'pedro@email.com',
                'plan': 'Premium 100Mbps',
                'fee': 1899,
                'status': 'Active',
                'due_date': '2026-06-28',
                'balance': 0,
                'joined': '2023-11-05'
            },
            {
                'client_id': 'C005',
                'name': 'Rosa Mendoza',
                'address': '654 Aguinaldo Rd, Brgy. Central',
                'phone': '09211234567',
                'email': 'rosa@email.com',
                'plan': 'Standard 50Mbps',
                'fee': 1299,
                'status': 'Overdue',
                'due_date': '2026-06-08',
                'balance': 1299,
                'joined': '2024-02-14'
            },
        ]

        for client in clients_data:
            Client.objects.create(**client)
        self.stdout.write(self.style.SUCCESS(f'Created {len(clients_data)} clients'))

        # Create Applications
        applications_data = [
            {
                'app_id': 'APP-001',
                'name': 'Carlos Bautista',
                'phone': '09221234567',
                'email': 'carlos@email.com',
                'address': '888 Quezon Ave, Brgy. Malvar',
                'plan': 'Standard 50Mbps',
                'status': 'Pending',
                'date': '2026-06-12'
            },
            {
                'app_id': 'APP-002',
                'name': 'Liza Villanueva',
                'phone': '09231234567',
                'email': 'liza@email.com',
                'address': '567 Taft Ave, Brgy. Tejeros',
                'plan': 'Premium 100Mbps',
                'status': 'Pending',
                'date': '2026-06-14'
            },
            {
                'app_id': 'APP-003',
                'name': 'Roberto Aquino',
                'phone': '09241234567',
                'email': 'roberto@email.com',
                'address': '234 Roxas Blvd, Brgy. Pasay',
                'plan': 'Basic 25Mbps',
                'status': 'Approved',
                'date': '2026-06-10'
            },
            {
                'app_id': 'APP-004',
                'name': 'Elena Torres',
                'phone': '09251234567',
                'email': 'elena@email.com',
                'address': '901 España Blvd, Brgy. Sampaloc',
                'plan': 'Standard 50Mbps',
                'status': 'Declined',
                'date': '2026-06-08'
            },
        ]

        for app in applications_data:
            Application.objects.create(**app)
        self.stdout.write(self.style.SUCCESS(f'Created {len(applications_data)} applications'))

        # Create Tickets
        tickets_data = [
            {
                'ticket_id': 'TKT-2026-001',
                'client': 'Maria Santos',
                'category': 'Slow Speed',
                'priority': 'High',
                'status': 'In Progress',
                'description': 'Internet speed dropping to 5Mbps during peak hours',
                'assigned': 'Technician Alvaro',
                'created': '2026-06-13'
            },
            {
                'ticket_id': 'TKT-2026-002',
                'client': 'Juan dela Cruz',
                'category': 'Billing Concern',
                'priority': 'Medium',
                'status': 'Open',
                'description': 'Charged incorrectly for last month',
                'assigned': 'Unassigned',
                'created': '2026-06-14'
            },
            {
                'ticket_id': 'TKT-2026-003',
                'client': 'Rosa Mendoza',
                'category': 'Frequent Disconnection',
                'priority': 'Critical',
                'status': 'Open',
                'description': 'Connection drops every 30 minutes throughout the day',
                'assigned': 'Unassigned',
                'created': '2026-06-15'
            },
            {
                'ticket_id': 'TKT-2026-004',
                'client': 'Pedro Garcia',
                'category': 'Technical Support',
                'priority': 'Low',
                'status': 'Resolved',
                'description': 'Router configuration assistance needed',
                'assigned': 'Technician Bernal',
                'created': '2026-06-11'
            },
        ]

        for ticket in tickets_data:
            Ticket.objects.create(**ticket)
        self.stdout.write(self.style.SUCCESS(f'Created {len(tickets_data)} tickets'))

        # Create Payments
        payments_data = [
            {
                'payment_id': 'PAY-001',
                'client': 'Maria Santos',
                'date': '2026-06-15',
                'amount': 1899,
                'period': 'June 2026',
                'method': 'GCash',
                'status': 'Verified'
            },
            {
                'payment_id': 'PAY-002',
                'client': 'Juan dela Cruz',
                'date': '2026-06-14',
                'amount': 1299,
                'period': 'June 2026',
                'method': 'Cash',
                'status': 'Pending'
            },
            {
                'payment_id': 'PAY-003',
                'client': 'Rosa Mendoza',
                'date': '2026-06-13',
                'amount': 1299,
                'period': 'June 2026',
                'method': 'GCash',
                'status': 'Rejected'
            },
            {
                'payment_id': 'PAY-004',
                'client': 'Pedro Garcia',
                'date': '2026-06-12',
                'amount': 1899,
                'period': 'June 2026',
                'method': 'GCash',
                'status': 'Verified'
            },
        ]

        for payment in payments_data:
            Payment.objects.create(**payment)
        self.stdout.write(self.style.SUCCESS(f'Created {len(payments_data)} payments'))

        self.stdout.write(self.style.SUCCESS('Successfully loaded all initial data!'))
