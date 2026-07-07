"""
GCash Payment Integration Service
Handles GCash API calls and payment processing
"""
import calendar
import requests
import json
import uuid
from datetime import date
from decimal import Decimal
from .models import Payment, Client


def _add_months(start_date, months):
    """Return a date with the given number of months added."""
    month = start_date.month - 1 + months
    year = start_date.year + month // 12
    month = month % 12 + 1
    day = min(start_date.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


class GCashService:
    """Service for handling GCash payments"""
    
    # GCash API Configuration
    # Set USE_MOCK_MODE = True for testing without real credentials
    USE_MOCK_MODE = True  # Set to False when you have real GCash credentials
    
    # Mock Payment URLs (for testing)
    MOCK_SUCCESS_URL = "http://localhost:8000/client/gcash-callback/?status=success&reference_id="
    
    # Real GCash API Configuration
    # Note: Replace these with your actual GCash credentials
    GCASH_API_BASE_URL = "https://api.gcash.ph/v1"  # GCash sandbox/production URL
    GCASH_MERCHANT_ID = "YOUR_MERCHANT_ID"
    GCASH_API_KEY = "YOUR_API_KEY"
    GCASH_SECRET_KEY = "YOUR_SECRET_KEY"
    
    @staticmethod
    def generate_reference_id():
        """Generate unique reference ID for payment"""
        return f"PAY-{date.today().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}"
    
    @staticmethod
    def create_payment_link(client_email, amount, description, callback_url):
        """
        Create a GCash payment link
        
        Args:
            client_email: Client email address
            amount: Payment amount in PHP
            description: Payment description
            callback_url: URL to return to after payment
            
        Returns:
            dict with payment_link and reference_id
        """
        reference_id = GCashService.generate_reference_id()
        
        # If in mock mode, return mock payment link
        if GCashService.USE_MOCK_MODE:
            # In mock mode, return a test payment link on the same host as the callback
            try:
                from urllib.parse import urlparse
                parsed = urlparse(callback_url)
                mock_host = f"{parsed.scheme}://{parsed.netloc}"
            except Exception:
                mock_host = "http://localhost:8000"

            mock_payment_link = f"{mock_host}/test-gcash-payment/?reference_id={reference_id}&amount={amount}"
            return {
                "success": True,
                "reference_id": reference_id,
                "payment_link": mock_payment_link,
                "amount": float(amount),
                "status": "pending",
                "is_mock": True
            }
        
        # Create payment payload for real GCash API
        payload = {
            "amount": float(amount),
            "currency": "PHP",
            "description": description,
            "reference_id": reference_id,
            "customer": {
                "email": client_email,
            },
            "redirect_url": callback_url,
        }
        
        try:
            # Make API call to GCash
            headers = {
                "Authorization": f"Bearer {GCashService.GCASH_API_KEY}",
                "Content-Type": "application/json",
            }
            
            # Call real GCash API
            response = requests.post(
                f"{GCashService.GCASH_API_BASE_URL}/payments",
                json=payload,
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 201:
                data = response.json()
                return {
                    "success": True,
                    "reference_id": reference_id,
                    "payment_link": data.get("payment_link"),
                    "amount": float(amount),
                    "status": "pending"
                }
            else:
                return {
                    "success": False,
                    "error": f"GCash API error: {response.status_code}"
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    @staticmethod
    def verify_payment(reference_id):
        """
        Verify payment status with GCash
        
        Args:
            reference_id: GCash reference ID
            
        Returns:
            dict with payment status
        """
        try:
            headers = {
                "Authorization": f"Bearer {GCashService.GCASH_API_KEY}",
                "Content-Type": "application/json",
            }
            
            # In production, this would call: GET /payments/{reference_id}
            # For now, return mock response
            response = {
                "success": True,
                "reference_id": reference_id,
                "status": "completed",
                "amount": 0.0
            }
            
            return response
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    @staticmethod
    def process_webhook_payment(webhook_data):
        """
        Process payment from GCash webhook
        Automatically creates Payment record
        
        Args:
            webhook_data: Data received from GCash webhook
            
        Returns:
            dict with processing result
        """
        try:
            reference_id = webhook_data.get('reference_id')
            status = webhook_data.get('status')
            amount = webhook_data.get('amount')
            client_email = webhook_data.get('customer_email')
            
            # Find client
            client = Client.objects.filter(email=client_email).first()
            if not client:
                return {
                    "success": False,
                    "error": "Client not found"
                }
            
            # Create payment record
            payment_id = f"GC{uuid.uuid4().hex[:8].upper()}"
            
            payment = Payment.objects.create(
                payment_id=payment_id,
                client=client.name,
                date=date.today(),
                amount=Decimal(str(amount)),
                period=f"{date.today().strftime('%B %Y')}",
                method="GCash",
                status="Verified" if status == "completed" else "Pending"
            )
            
            # Update client balance if payment verified
            if status == "completed":
                payment_amount = Decimal(str(amount))
                from dashboard.client_views import _apply_payment_coverage
                client = _apply_payment_coverage(client, payment_amount)
            
            return {
                "success": True,
                "payment_id": payment_id,
                "status": payment.status,
                "message": "Payment recorded successfully"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
