from datetime import datetime, timedelta
import uuid
from decimal import Decimal
from django.conf import settings
from django.utils import timezone
from django.core.mail import EmailMultiAlternatives

# Mock/Test Mode Toggle loaded from settings. In production set NOTIFICATIONS_USE_MOCK=False
NOTIFICATIONS_USE_MOCK = getattr(settings, 'NOTIFICATIONS_USE_MOCK', True)
NOTIFICATIONS_USE_MOCK_SMS = getattr(settings, 'NOTIFICATIONS_USE_MOCK_SMS', False)
DEFAULT_EMAIL_SENDER = getattr(settings, 'DEFAULT_FROM_EMAIL', 'billing@netconnect-isp.com')
MOCK_EMAIL_SENDER = "billing@netconnect-isp.com"
MOCK_SMS_PROVIDER = "NetConnect Billing SMS"
TWILIO_ACCOUNT_SID = getattr(settings, 'TWILIO_ACCOUNT_SID', '')
TWILIO_AUTH_TOKEN = getattr(settings, 'TWILIO_AUTH_TOKEN', '')
TWILIO_PHONE_NUMBER = getattr(settings, 'TWILIO_PHONE_NUMBER', '')


class NotificationService:
    """
    Handles sending notifications for overdue payments.
    Can operate in mock mode (development) or real mode (production).
    Logs all notifications to database for audit trail.
    Uses editable templates from NotificationTemplate model.
    """
    
    # Fallback templates (used if database templates not available)
    DEFAULT_TEMPLATES = {
        'First Notice': {
            'subject': 'Payment Reminder: Your Internet Bill is Due',
            'email_body': '''Dear {client_name},

This is a friendly reminder that your internet bill payment is now due.

📊 Bill Details:
  • Account: {client_id}
  • Plan: {plan}
  • Amount Due: ₱{amount_due:.2f}
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
NetConnect ISP Billing Team''',
            'sms_body': 'NetConnect: Your bill of ₱{amount_due:.2f} is now due. Pay within 3 days to avoid disconnection. Visit your account portal to pay.'
        },
        'Second Notice': {
            'subject': 'URGENT: Payment Due - Internet Bill Past Due',
            'email_body': '''Dear {client_name},

⚠️ URGENT NOTICE ⚠️

Your internet bill payment is now OVERDUE and you have {days_remaining} days remaining before service disconnection.

📊 Overdue Bill Details:
  • Account: {client_id}
  • Plan: {plan}
  • Amount Overdue: ₱{amount_due:.2f}
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

NetConnect ISP Billing Team''',
            'sms_body': 'URGENT: NetConnect - Your bill of ₱{amount_due:.2f} is overdue! You have {days_remaining} days before disconnection. Pay now!'
        },
        'Disconnection Warning': {
            'subject': 'FINAL NOTICE: Internet Disconnection Imminent',
            'email_body': '''Dear {client_name},

🔴 FINAL NOTICE - DISCONNECTION IMMINENT 🔴

Your internet service will be DISCONNECTED WITHIN 24 HOURS if payment is not received.

📊 Critical Bill Details:
  • Account: {client_id}
  • Plan: {plan}
  • Amount Overdue: ₱{amount_due:.2f}
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

NetConnect ISP Billing Team''',
            'sms_body': '⛔ NetConnect FINAL: Your ₱{amount_due:.2f} bill is overdue {days_overdue} days. Service DISCONNECTS in 24h. PAY NOW or visit portal!'
        },
        'Payment Receipt': {
            'subject': 'Payment Receipt from NetConnect ISP',
            'email_body': '''Dear {client_name},

Thank you for your payment.

📄 Payment Receipt
  • Account: {client_id}
  • Plan: {plan}
  • Amount Paid: ₱{amount_paid:.2f}
  • Payment ID: {payment_id}
  • Payment Method: {payment_method}
  • Date: {payment_date}
  • New Balance: ₱{new_balance:.2f}

If you have any questions, reply to this email or contact our support team.

Thank you for choosing NetConnect ISP.

Best regards,
NetConnect ISP Billing Team''',
            'sms_body': 'Thank you for your payment of ₱{amount_paid:.2f}. A receipt has been sent to your email.'
        }
        ,
        'Service Scheduled': {
            'subject': 'Support Visit Scheduled - {ticket_id}',
            'email_body': '''Hi {client_name},

Our technician is scheduled to visit on {date} {time}.

Issue: {issue}

Please make sure someone is available at {address}.

If you need to reschedule, reply to this message or contact our support team.

Best regards,
NetConnect Support Team''',
            'sms_body': 'Technician scheduled on {date} {time}. Issue: {issue}. Please ensure someone is at {address}.'
        },
        'Service Rescheduled': {
            'subject': 'Reschedule Approved - {ticket_id}',
            'email_body': '''Hi {client_name},

Your rescheduled date has been approved. We have updated the appointment and will notify the technician.

Scheduled visit: {date} {time}

Issue: {issue}

Please make sure someone is available at {address}.

If anything changes, please contact support.

Best regards,
NetConnect Support Team''',
            'sms_body': 'Your rescheduled date has been approved for {date} {time}. We have updated the appointment and will notify the technician. Please ensure someone is at {address}.'
        }
    }
    
    @staticmethod
    def get_template_from_database(notification_type, channel):
        """
        Fetch template from database.
        Falls back to DEFAULT_TEMPLATES if not found.
        
        Args:
            notification_type: 'First Notice', 'Second Notice', or 'Disconnection Warning'
            channel: 'Email' or 'SMS'
        
        Returns:
            {'body': ..., 'subject': ...} for email or {'body': ...} for SMS
        """
        from api.models import NotificationTemplate
        
        try:
            template = NotificationTemplate.objects.get(
                template_type=notification_type,
                channel=channel
            )
            if channel == 'Email':
                return {
                    'body': template.body,
                    'subject': template.subject
                }
            else:  # SMS
                return {
                    'body': template.body,
                    'subject': ''  # SMS doesn't use subject
                }
        except NotificationTemplate.DoesNotExist:
            # Fall back to default template
            default = NotificationService.DEFAULT_TEMPLATES.get(notification_type, {})
            if channel == 'Email':
                return {
                    'body': default.get('email_body', ''),
                    'subject': default.get('subject', '')
                }
            else:  # SMS
                return {
                    'body': default.get('sms_body', ''),
                    'subject': ''
                }
        except Exception as e:
            # If any error, use default
            print(f"Error fetching template: {e}")
            default = NotificationService.DEFAULT_TEMPLATES.get(notification_type, {})
            if channel == 'Email':
                return {
                    'body': default.get('email_body', ''),
                    'subject': default.get('subject', '')
                }
            else:  # SMS
                return {
                    'body': default.get('sms_body', ''),
                    'subject': ''
                }
    
    @staticmethod
    def get_notification_type(days_overdue):
        """
        Determine notification type based on days overdue.
        """
        if days_overdue <= 1:
            return 'First Notice'
        elif days_overdue <= 3:
            return 'Second Notice'
        else:
            return 'Disconnection Warning'
    
    @staticmethod
    def log_sms(client_id, customer_name, mobile_number, notification_type, message_content, amount_due=None):
        """
        Legacy SMS logging method retained for compatibility only.
        Actual notification persistence is no longer stored in SMSNotificationLog.
        """
        return None
    
    @staticmethod
    def _safe_print(*args, **kwargs):
        """Print text safely on consoles with limited encodings."""
        try:
            print(*args, **kwargs)
        except UnicodeEncodeError:
            safe_args = []
            for arg in args:
                if isinstance(arg, str):
                    safe_args.append(arg.encode('ascii', 'backslashreplace').decode('ascii'))
                else:
                    safe_args.append(arg)
            print(*safe_args, **kwargs)

    @staticmethod
    def log_email(client_id, customer_name, email_address, notification_type, subject, message_content, amount_due=None, status='Simulated Sent'):
        """
        Legacy Email logging method retained for compatibility only.
        Actual notification persistence is no longer stored in EmailNotificationLog.
        """
        return None
    
    @staticmethod
    def send_email(recipient_email, subject, body, client_id, customer_name, notification_type, amount_due=None):
        """
        Send email notification and log to database.
        In mock mode: Logs to console and database.
        In production: Uses Django email backend.
        """
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        if NOTIFICATIONS_USE_MOCK:
            # Mock mode - do not persist email logs to DB (removed per new requirement)
            NotificationService._safe_print(f"Mock email sent to {recipient_email}")
            return {
                'status': 'success',
                'message': 'Mock email sent (not logged)',
                'recipient': recipient_email,
                'timestamp': timestamp
            }
        else:
            try:
                email_message = EmailMultiAlternatives(
                    subject=subject,
                    body=body,
                    from_email=DEFAULT_EMAIL_SENDER,
                    to=[recipient_email]
                )
                email_message.send(fail_silently=False)

                return {
                    'status': 'success',
                    'message': 'Email sent successfully',
                    'recipient': recipient_email
                }
            except Exception as e:
                # Return error without creating persistent log
                return {
                    'status': 'error',
                    'message': str(e),
                    'recipient': recipient_email
                }

    @staticmethod
    def send_payment_receipt(client_id, client_name, recipient_email, amount_paid, payment_id, payment_method, payment_date, new_balance, plan=None):
        """
        Send a payment receipt email to the customer and log it.
        """
        notification_type = 'Payment Receipt'
        template = NotificationService.get_template_from_database(notification_type, 'Email')
        format_vars = {
            'client_id': client_id,
            'client_name': client_name,
            'customer_name': client_name,
            'plan': plan or '',
            'amount_paid': float(amount_paid),
            'payment_id': payment_id,
            'payment_method': payment_method,
            'payment_date': payment_date.strftime('%B %d, %Y') if hasattr(payment_date, 'strftime') else str(payment_date),
            'new_balance': float(new_balance),
        }
        email_body = template['body'].format(**format_vars)
        subject = template['subject']
        return NotificationService.send_email(
            recipient_email=recipient_email,
            subject=subject,
            body=email_body,
            client_id=client_id,
            customer_name=client_name,
            notification_type=notification_type,
            amount_due=amount_paid
        )

    @staticmethod
    def send_sms(phone_number, message, client_id, customer_name, notification_type, amount_due=None):
        """
        Send SMS notification and log to database.
        In mock mode: Logs to console and database.
        In production: Uses Twilio API.
        """
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        if NOTIFICATIONS_USE_MOCK or NOTIFICATIONS_USE_MOCK_SMS:
            # Mock mode - log to console and database
            NotificationService._safe_print(f"\n{'='*70}")
            NotificationService._safe_print("MOCK SMS SENT")
            NotificationService._safe_print(f"{'='*70}")
            NotificationService._safe_print(f"To: {phone_number}")
            NotificationService._safe_print(f"Message: {message}")
            NotificationService._safe_print(f"Timestamp: {timestamp}")
            NotificationService._safe_print(f"{'='*70}\n")
            
            # Mock mode - do not persist SMS logs to DB (removed per new requirement)
            NotificationService._safe_print(f"Mock SMS sent to {phone_number}")
            return {
                'status': 'success',
                'message': 'Mock SMS sent (not logged)',
                'recipient': phone_number,
                'timestamp': timestamp
            }
        else:
            # Production mode - send real SMS via Twilio
            try:
                if not all([TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER]):
                    return {
                        'status': 'error',
                        'message': 'Twilio credentials not configured'
                    }
                
                from twilio.rest import Client
                client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
                
                sms_message = client.messages.create(
                    body=message,
                    from_=TWILIO_PHONE_NUMBER,
                    to=phone_number
                )
                
                # Production: do not persist separate SMS log record here
                return {
                    'status': 'success',
                    'message': 'SMS sent successfully',
                    'recipient': phone_number,
                    'sms_id': sms_message.sid
                }
            except Exception as e:
                return {
                    'status': 'error',
                    'message': str(e)
                }
    
    @staticmethod
    def ensure_overdue_notification(client, days_overdue=None, force=False):
        """
        Create an overdue notification automatically when a client enters a new overdue or disconnection state.
        """
        from api.models import OverdueNotification

        if not client:
            return None

        if days_overdue is None:
            if not getattr(client, 'due_date', None):
                return None
            days_overdue = max(0, (timezone.localdate() - client.due_date).days)

        if days_overdue <= 0:
            return None

        notification_type = NotificationService.get_notification_type(days_overdue)
        target_status = 'Disconnected' if days_overdue > 3 else 'Overdue'

        last_notification = OverdueNotification.objects.filter(client=client.client_id).order_by('-sent_at').first()
        if not force and last_notification and last_notification.notification_type == notification_type:
            return None

        result = NotificationService.send_overdue_notification(
            client_id=client.client_id,
            client_name=client.name,
            phone_number=client.phone,
            email=client.email,
            plan=client.plan,
            amount_due=client.balance or Decimal('0.00'),
            due_date=client.due_date,
            days_overdue=days_overdue,
        )

        notification_count = OverdueNotification.objects.count() + 1
        notification_id = f'NOTIF{str(notification_count).zfill(4)}'
        notification = OverdueNotification.objects.create(
            notification_id=notification_id,
            client=client.client_id,
            notification_type=notification_type,
            amount_due=client.balance or Decimal('0.00'),
            days_overdue=days_overdue,
            status='Sent' if result['email'].get('status') == 'success' or result['sms'].get('status') == 'success' else 'Failed',
            email_sent=result['email'].get('status') == 'success',
            sms_sent=result['sms'].get('status') == 'success',
            email_response=str(result['email']),
            sms_response=str(result['sms']),
            sent_at=timezone.now(),
        )

        client.status = target_status
        client.save(update_fields=['status'])
        return notification

    @staticmethod
    def send_overdue_notification(client_id, client_name, phone_number, email, 
                                  plan, amount_due, due_date, days_overdue):
        """
        Send complete overdue notification (Email + SMS) and log to database.
        Uses templates from NotificationTemplate model (or falls back to defaults).
        Returns notification results with logging info.
        """
        notification_type = NotificationService.get_notification_type(days_overdue)
        
        # Get templates from database
        email_template = NotificationService.get_template_from_database(notification_type, 'Email')
        sms_template = NotificationService.get_template_from_database(notification_type, 'SMS')
        
        # Calculate days remaining
        days_remaining = max(0, 3 - days_overdue)
        
        # Format message with variables
        format_vars = {
            'client_id': client_id,
            'client_name': client_name,
            'customer_name': client_name,
            'plan': plan,
            'amount_due': float(amount_due),
            'due_date': due_date.strftime('%B %d, %Y') if hasattr(due_date, 'strftime') else str(due_date),
            'days_overdue': days_overdue,
            'days_remaining': days_remaining
        }
        
        email_body = email_template['body'].format(**format_vars)
        sms_body = sms_template['body'].format(**format_vars)
        subject = email_template['subject']
        
        # Send email
        email_result = NotificationService.send_email(
            recipient_email=email,
            subject=subject,
            body=email_body,
            client_id=client_id,
            customer_name=client_name,
            notification_type=notification_type,
            amount_due=amount_due
        )
        
        # Send SMS
        sms_result = NotificationService.send_sms(
            phone_number=phone_number,
            message=sms_body,
            client_id=client_id,
            customer_name=client_name,
            notification_type=notification_type,
            amount_due=amount_due
        )
        
        return {
            'notification_type': notification_type,
            'email': email_result,
            'sms': sms_result,
            'template': {
                'subject': subject,
                'email_preview': email_body[:200] + '...',
                'sms_preview': sms_body
            }
        }
