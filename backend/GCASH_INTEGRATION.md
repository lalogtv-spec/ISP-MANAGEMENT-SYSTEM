# GCash Payment Integration Setup Guide

This document provides instructions for setting up and using the GCash payment integration in the NetConnect ISP system.

## Overview

The GCash integration allows clients to:
- Pay their bills directly from the client portal
- Receive automatic payment verification and recording
- View payment history automatically updated
- Admin can see payments in the payments panel automatically

## Features Implemented

### 1. Client Portal Payment Page
- **Location**: `/client/gcash-payment/`
- Displays client information
- Allows amount input (validates against outstanding balance)
- Shows accepted payment methods
- Secure payment form

### 2. Automatic Payment Recording
- Payments are automatically recorded when verified
- Payment status appears in client's payment history instantly
- Client balance is automatically updated

### 3. Admin Panel Integration
- Payments appear in the admin payments panel
- Payment method shows as "GCash"
- Can filter and search payments

### 4. Webhook Support
- Endpoint: `/api/gcash-webhook/`
- Receives payment notifications from GCash
- Automatically processes and verifies payments
- No manual admin action required

## Configuration

### Step 1: Update GCash Credentials

Edit `backend/api/gcash_service.py` and replace with your GCash credentials:

```python
GCASH_API_BASE_URL = "https://api.gcash.ph/v1"  # or sandbox URL
GCASH_MERCHANT_ID = "YOUR_MERCHANT_ID"
GCASH_API_KEY = "YOUR_API_KEY"
GCASH_SECRET_KEY = "YOUR_SECRET_KEY"
```

### Step 2: Configure GCash Merchant Account

1. Log in to your GCash Merchant Portal
2. Go to API Settings
3. Set webhook URL to: `https://yourdomain.com/api/gcash-webhook/`
4. Generate and save your API credentials
5. Update the credentials in `gcash_service.py`

### Step 3: Environment Variables (Optional but Recommended)

Create a `.env` file in the backend directory:

```
GCASH_MERCHANT_ID=your_merchant_id
GCASH_API_KEY=your_api_key
GCASH_SECRET_KEY=your_secret_key
GCASH_API_BASE_URL=https://api.gcash.ph/v1
```

Then update `gcash_service.py` to use environment variables:

```python
import os
from dotenv import load_dotenv

load_dotenv()

GCASH_MERCHANT_ID = os.getenv('GCASH_MERCHANT_ID')
GCASH_API_KEY = os.getenv('GCASH_API_KEY')
GCASH_SECRET_KEY = os.getenv('GCASH_SECRET_KEY')
GCASH_API_BASE_URL = os.getenv('GCASH_API_BASE_URL', "https://api.gcash.ph/v1")
```

## User Flow

### For Clients:
1. Client logs in to portal
2. Goes to Payments section
3. Sees outstanding balance
4. Clicks "Pay Now via GCash"
5. Enters payment amount (auto-filled with outstanding balance)
6. Agrees to terms and conditions
7. Clicks "Pay Now via GCash"
8. Redirected to GCash payment page
9. Completes payment via GCash app or QR code
10. Returns to portal with payment confirmation
11. Payment automatically appears in payment history

### For Admin:
1. Login to admin panel
2. Go to Payments section
3. See newly received payments with status "Verified"
4. Payment method shows as "GCash"
5. Can view, filter, and search payments

## API Endpoints

### Payment Request (Client Portal)
- **URL**: `/client/gcash-payment/`
- **Method**: GET/POST
- **Auth**: Login Required
- **Response**: Payment form or redirect to GCash

### Payment Callback
- **URL**: `/client/gcash-callback/`
- **Method**: GET
- **Params**: 
  - `reference_id`: GCash reference ID
  - `status`: Payment status (completed/pending/failed)

### Webhook Endpoint (GCash Server)
- **URL**: `/api/gcash-webhook/`
- **Method**: POST
- **Auth**: Signature verification
- **Payload**:
```json
{
  "reference_id": "PAY-20260617-ABC123",
  "status": "completed",
  "amount": 1299.00,
  "customer_email": "client@example.com"
}
```

## Database Schema Updates

### Payment Model Extensions
The Payment model now includes:
- `payment_id`: Unique GCash payment identifier
- `client`: Client name for quick lookup
- `date`: Payment date
- `amount`: Payment amount in PHP
- `period`: Billing period (auto-filled with current month)
- `method`: Payment method (GCash)
- `status`: Payment status (Pending/Verified/Rejected)

## Security Considerations

### Current Implementation (Testing/Development)
- Uses mock API responses
- No signature verification (for testing)

### Production Implementation
You MUST implement:

1. **Webhook Signature Verification**
```python
import hmac
import hashlib

def verify_webhook_signature(signature, body, secret):
    expected_sig = hmac.new(
        secret.encode(),
        body,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(signature, expected_sig)
```

2. **HTTPS Only**
- All callbacks must use HTTPS
- Configure in Django settings:
```python
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
```

3. **Request Validation**
- Verify request source IP from GCash
- Validate payment amounts
- Check for duplicate submissions

4. **Rate Limiting**
- Implement webhook rate limiting
- Prevent replay attacks

## Testing

### Manual Testing

1. **Test Payment Page**
   - Navigate to: `http://localhost:8000/client/gcash-payment/`
   - Should see form with client information
   - Enter test amount

2. **Test Webhook**
```bash
curl -X POST http://localhost:8000/api/gcash-webhook/ \
  -H "Content-Type: application/json" \
  -d '{
    "reference_id": "TEST-001",
    "status": "completed",
    "amount": 500.00,
    "customer_email": "testpending@test.com"
  }'
```

3. **Check Payment Recording**
   - Visit payments panel
   - Verify payment appears with status "Verified"
   - Check client balance updated

### Test Users
- Username: `testpending`
- Email: `pending@test.com`
- Outstanding Balance: ₱499.00 (Basic plan)

## Troubleshooting

### Payment Not Appearing
1. Check webhook endpoint is accessible
2. Verify GCash credentials
3. Check Django logs for errors
4. Verify client email matches

### Payment Status Not Updating
1. Ensure webhook URL is correctly configured in GCash portal
2. Check firewall allows incoming webhooks
3. Verify signature validation (if enabled)

### CSRF Token Errors
1. Ensure CSRF middleware is enabled
2. Verify `{% csrf_token %}` in payment form
3. Check CSRF cookie settings

## Future Enhancements

1. **Payment Plans**
   - Allow installment payments
   - Auto-payment on due dates

2. **Receipt Generation**
   - PDF receipts
   - Email receipts

3. **Refund Processing**
   - Auto refunds for overpayments
   - Admin refund interface

4. **Analytics**
   - Payment trends
   - Failed payment analytics
   - Revenue forecasting

5. **Multiple Payment Methods**
   - Debit/Credit cards
   - Bank transfers
   - Maya integration

## Support

For GCash API documentation: https://docs.gcash.ph
For NetConnect support: support@netconnect.ph

---

**Last Updated**: June 2026
**Version**: 1.0
