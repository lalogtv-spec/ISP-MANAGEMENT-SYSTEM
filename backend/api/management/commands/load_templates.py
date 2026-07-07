from django.core.management.base import BaseCommand
from api.models import NotificationTemplate

class Command(BaseCommand):
    help = 'Load default notification templates'

    def handle(self, *args, **options):
        templates_data = [
            {
                'template_id': 'First_Notice_Email',
                'template_type': 'First Notice',
                'channel': 'Email',
                'subject': 'Payment Reminder: Your Internet Bill is Due',
                'body': '''Dear {customer_name},

This is a friendly reminder that your internet bill payment is now due.

📊 Bill Details:
  • Account: {client_id}
  • Plan: {plan}
  • Amount Due: ₱{amount_due}
  • Due Date: {due_date}

⏰ Payment Grace Period: 3 days from due date
After 3 days without payment, your internet service will be suspended.

💳 Payment Methods:
  • GCash
  • Bank Transfer
  • Over the Counter

🔗 Pay Now: Click the payment link in your account portal

Thank you for your business!

Best regards,
NetConnect ISP Billing Team'''
            },
            {
                'template_id': 'First_Notice_SMS',
                'template_type': 'First Notice',
                'channel': 'SMS',
                'subject': '',
                'body': 'NetConnect: Your bill of ₱{amount_due} is now due. Pay within 3 days to avoid disconnection. Visit your account portal to pay.'
            },
            {
                'template_id': 'Second_Notice_Email',
                'template_type': 'Second Notice',
                'channel': 'Email',
                'subject': 'URGENT: Payment Due - Internet Bill Past Due',
                'body': '''Dear {customer_name},

⚠️ URGENT NOTICE ⚠️

Your internet bill payment is now OVERDUE and you have {days_remaining} days remaining before service disconnection.

📊 Overdue Bill Details:
  • Account: {client_id}
  • Plan: {plan}
  • Amount Overdue: ₱{amount_due}
  • Overdue Days: {days_overdue}
  • Due Date: {due_date}

🚨 IMPORTANT: Your internet service will be disconnected if payment is not received within {days_remaining} days.

💳 Payment Methods:
  • GCash
  • Bank Transfer
  • Over the Counter

🔗 Pay Immediately: Click the payment link in your account portal

If you have already made payment, please disregard this notice.

Contact us if you need assistance with payment.

NetConnect ISP Billing Team'''
            },
            {
                'template_id': 'Second_Notice_SMS',
                'template_type': 'Second Notice',
                'channel': 'SMS',
                'subject': '',
                'body': 'URGENT: NetConnect - Your bill of ₱{amount_due} is overdue! You have {days_remaining} days before disconnection. Pay now!'
            },
            {
                'template_id': 'Disconnection_Warning_Email',
                'template_type': 'Disconnection Warning',
                'channel': 'Email',
                'subject': 'FINAL NOTICE: Internet Disconnection Imminent',
                'body': '''Dear {customer_name},

🔴 FINAL NOTICE - DISCONNECTION IMMINENT 🔴

Your internet service will be DISCONNECTED WITHIN 24 HOURS if payment is not received.

📊 Critical Bill Details:
  • Account: {client_id}
  • Plan: {plan}
  • Amount Overdue: ₱{amount_due}
  • Days Overdue: {days_overdue} days
  • Due Date: {due_date}
  • Deadline: 24 hours from this notice

⚡ ACT NOW - Payment Required Immediately

💳 Payment Methods:
  • GCash (Fastest)
  • Bank Transfer
  • Over the Counter

🔗 PAY NOW: Click the payment link in your account portal

Once your payment is received, reconnection will be processed within 2 hours.

For emergencies or assistance, contact us immediately.

NetConnect ISP Billing Team'''
            },
            {
                'template_id': 'Disconnection_Warning_SMS',
                'template_type': 'Disconnection Warning',
                'channel': 'SMS',
                'subject': '',
                'body': '⛔ NetConnect FINAL: Your ₱{amount_due} bill is overdue {days_overdue} days. Service DISCONNECTS in 24h. PAY NOW or visit portal!'
            },
            {
                'template_id': 'Service_Scheduled_Email',
                'template_type': 'Service Scheduled',
                'channel': 'Email',
                'subject': 'Support Visit Scheduled - {ticket_id}',
                'body': '''Hi {customer_name},

Your support visit has been scheduled for {date} {time}.

Issue: {issue}

Please make sure someone is available at {address}.

If you need to reschedule, reply to this message or contact our support team.

Best regards,
NetConnect Support Team'''
            },
            {
                'template_id': 'Service_Scheduled_SMS',
                'template_type': 'Service Scheduled',
                'channel': 'SMS',
                'subject': '',
                'body': 'Your support visit is scheduled for {date} {time}. Issue: {issue}. Please have someone ready at {address}.'
            },
            {
                'template_id': 'Service_Rescheduled_Email',
                'template_type': 'Service Rescheduled',
                'channel': 'Email',
                'subject': 'Reschedule Approved - {ticket_id}',
                'body': '''Hi {customer_name},

Your rescheduled date has been approved. We have updated the appointment and will notify the technician.

Scheduled visit: {date} {time}

Issue: {issue}

Please make sure someone is available at {address}.

If anything changes, please contact support.

Best regards,
NetConnect Support Team'''
            },
            {
                'template_id': 'Service_Rescheduled_SMS',
                'template_type': 'Service Rescheduled',
                'channel': 'SMS',
                'subject': '',
                'body': 'Your rescheduled date has been approved for {date} {time}. We have updated the appointment and will notify the technician. Please ensure someone is at {address}.'
            },
        ]

        created_count = 0
        for template_data in templates_data:
            template, created = NotificationTemplate.objects.get_or_create(
                template_id=template_data['template_id'],
                defaults={
                    'template_type': template_data['template_type'],
                    'channel': template_data['channel'],
                    'subject': template_data['subject'],
                    'body': template_data['body'],
                }
            )
            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f'✓ Created: {template.template_id}'))
            else:
                self.stdout.write(self.style.WARNING(f'ℹ️  Already exists: {template.template_id}'))

        self.stdout.write(self.style.SUCCESS(f'\n✓ Total templates created: {created_count}'))
