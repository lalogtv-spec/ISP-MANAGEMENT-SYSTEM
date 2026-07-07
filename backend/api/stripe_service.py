import calendar
import uuid

import stripe
from django.conf import settings
from decimal import Decimal
from datetime import date
from api.models import Client, Payment

stripe.api_key = getattr(settings, 'STRIPE_API_KEY', '')


def _add_months(start_date, months):
    """Add months to a date while keeping the day valid for the month."""
    month = start_date.month - 1 + months
    year = start_date.year + month // 12
    month = month % 12 + 1
    day = min(start_date.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


class StripeService:
    @staticmethod
    def create_checkout_session(client, amount, payment_type, months, description, success_url, cancel_url):
        try:
            if not settings.STRIPE_API_KEY:
                return {'success': False, 'error': 'Stripe API key is not configured.'}

            # Stripe requires amount in cents
            amount_cents = int(Decimal(str(amount)) * 100)

            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                mode='payment',
                line_items=[{
                    'price_data': {
                        'currency': 'php',
                        'product_data': {
                            'name': description,
                        },
                        'unit_amount': amount_cents,
                    },
                    'quantity': 1,
                }],
                customer_email=client.email,
                success_url=success_url,
                cancel_url=cancel_url,
                metadata={
                    'client_id': client.client_id,
                    'client_name': client.name,
                    'payment_type': payment_type,
                    'months': str(months),
                    'plan': client.plan,
                }
            )

            return {
                'success': True,
                'payment_url': session.url,
                'session_id': session.id,
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @staticmethod
    def process_webhook(payload, sig_header):
        webhook_secret = getattr(settings, 'STRIPE_WEBHOOK_SECRET', '')
        if not webhook_secret:
            return {'success': False, 'error': 'Stripe webhook secret is not configured.'}

        try:
            event = stripe.Webhook.construct_event(
                payload=payload,
                sig_header=sig_header,
                secret=webhook_secret,
            )
        except Exception as e:
            return {'success': False, 'error': f'Invalid webhook signature: {e}'}

        if event['type'] == 'checkout.session.completed':
            session = event['data']['object']
            payment_intent = session.get('payment_intent')
            client_email = session.get('customer_email')
            amount_total = Decimal(session.get('amount_total', 0)) / 100
            metadata = session.get('metadata', {}) or {}
            client_id = metadata.get('client_id', '')
            client_name = metadata.get('client_name', '')
            payment_type = metadata.get('payment_type', 'current')
            months = int(metadata.get('months', '1') or 1)
            plan = metadata.get('plan', '')

            # Persist payment record
            client = Client.objects.filter(email=client_email).first()
            if not client:
                return {
                    'success': False,
                    'error': 'Client not found for Stripe payment email',
                }

            payment_id = f'STR{uuid.uuid4().hex[:7].upper()}'
            Payment.objects.create(
                payment_id=payment_id,
                client=client.name,
                date=date.today(),
                amount=amount_total,
                period=date.today().strftime('%B %Y'),
                method='Stripe',
                status='Verified'
            )

            payment_amount = Decimal(str(amount_total))
            from dashboard.client_views import _apply_payment_coverage
            client = _apply_payment_coverage(client, payment_amount)

            from api.notification_service import NotificationService
            NotificationService.send_payment_receipt(
                client_id=client.client_id,
                client_name=client.name,
                recipient_email=client.email,
                amount_paid=amount_total,
                payment_id=payment_id,
                payment_method='Stripe',
                payment_date=date.today(),
                new_balance=client.balance,
                plan=plan,
            )

            return {
                'success': True,
                'message': 'Stripe payment processed successfully',
                'payment_id': payment_id,
                'client_id': client_id,
                'client_name': client_name,
                'amount': float(amount_total),
                'payment_method': 'Stripe',
                'payment_type': payment_type,
                'months': months,
            }

        return {'success': True, 'message': 'Event received'}
