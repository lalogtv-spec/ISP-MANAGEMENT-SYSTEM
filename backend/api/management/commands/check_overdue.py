from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import datetime, date, timedelta
from decimal import Decimal
from api.models import Client, OverdueNotification, Payment
from api.notification_service import NotificationService


class Command(BaseCommand):
    help = 'Check for overdue clients and send notifications'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            dest='dry_run',
            help='Run without actually sending notifications',
        )
        parser.add_argument(
            '--client-id',
            type=str,
            dest='client_id',
            help='Check specific client by ID',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        specific_client = options.get('client_id', None)

        self.stdout.write(self.style.SUCCESS('Checking for overdue clients...'))
        self.stdout.write(f'Mode: {"DRY RUN" if dry_run else "LIVE"}')
        self.stdout.write('-' * 70)

        # Get clients to check
        query = Client.objects.filter(balance__gt=0)
        if specific_client:
            query = query.filter(client_id=specific_client)

        overdue_clients = []
        for client in query:
            days_overdue = (date.today() - client.due_date).days
            if days_overdue > 0:  # Payment is overdue
                overdue_clients.append({
                    'client': client,
                    'days_overdue': days_overdue
                })

        if not overdue_clients:
            self.stdout.write(self.style.WARNING('No overdue clients found.'))
            return

        self.stdout.write(
            self.style.WARNING(f'Found {len(overdue_clients)} overdue client(s)')
        )

        # Process each overdue client
        for client_info in overdue_clients:
            client = client_info['client']
            days_overdue = client_info['days_overdue']

            self.stdout.write(f"\n{'='*70}")
            self.stdout.write(f'Client: {client.client_id} - {client.name}')
            self.stdout.write(f'Days Overdue: {days_overdue}')
            self.stdout.write(f'Amount Due: ₱{client.balance:.2f}')
            self.stdout.write(f'Due Date: {client.due_date}')

            # Determine notification type
            notification_type = NotificationService.get_notification_type(days_overdue)
            self.stdout.write(f'Notification Type: {notification_type}')

            # Check if notification already sent today for this type
            today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
            existing_notification = OverdueNotification.objects.filter(
                client=client.client_id,
                notification_type=notification_type,
                sent_at__gte=today_start
            ).first()

            if existing_notification:
                self.stdout.write(
                    self.style.WARNING(f'Notification already sent today: {existing_notification.notification_id}')
                )
                continue

            self.stdout.write('Sending notifications...')

            if not dry_run:
                notification = NotificationService.ensure_overdue_notification(client, days_overdue=days_overdue)

                if notification:
                    self.stdout.write(self.style.SUCCESS(f'✓ Notification created: {notification.notification_id}'))
                    self.stdout.write(f'  Client status: {client.status}')
                else:
                    self.stdout.write(self.style.WARNING('No new overdue state change detected.'))

            else:
                # Dry run - just show what would be done
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
                self.stdout.write(self.style.SUCCESS(f'[DRY RUN] Would send: {notification_type}'))
                self.stdout.write(f'  Email: {client.email}')
                self.stdout.write(f'  SMS: {client.phone}')

        self.stdout.write(f'\n{'='*70}')
        self.stdout.write(self.style.SUCCESS('✓ Overdue check complete!'))
