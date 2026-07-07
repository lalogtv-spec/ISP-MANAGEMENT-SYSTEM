# Security Module - Quick Start Guide

## Installation (Already Completed ✓)

✅ Security module created and installed
✅ Database migrations applied
✅ All services implemented and tested
✅ Admin interface configured

---

## 5-Minute Setup

### 1. Configure Email (Gmail OTP)

**Prerequisite:** Your Gmail account must have 2-Factor Authentication enabled.

Steps:
1. Go to https://myaccount.google.com/apppasswords
2. Select "Mail" and your device type
3. Google will generate a 16-character password
4. Set environment variables:

```bash
# Windows PowerShell
$env:EMAIL_HOST_USER = "your-email@gmail.com"
$env:EMAIL_HOST_PASSWORD = "xxxx xxxx xxxx xxxx"  # 16-char password from Google

# Or add to .env file
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=xxxx xxxx xxxx xxxx
```

### 2. Generate Encryption Key

```bash
cd backend
python manage.py shell

# In Python shell
from cryptography.fernet import Fernet
key = Fernet.generate_key()
print(key.decode())

# Output: b'your-encryption-key...'
```

Set environment variable:
```bash
ENCRYPTION_KEY='your-encryption-key-from-above'
```

### 3. Install Additional Packages

```bash
pip install face-recognition opencv-python
# May take a few minutes the first time
```

---

## Testing the Features

### Test OTP via Gmail

```python
from django.contrib.auth.models import User
from security import OTPService

# Get a test user
user = User.objects.first()

# Send OTP
result = OTPService.send_otp(user, ip_address='127.0.0.1')
print(result['message'])  # Check your email!

# Verify (use code from email)
result = OTPService.verify_otp(user, otp_code='123456')
print(result['success'])  # Should be True
```

### Test Facial Recognition (Demo Mode)

```python
from security import FacialRecognitionService
import requests

# Download a test face image
url = 'https://upload.wikimedia.org/wikipedia/commons/thumb/3/3a/Cat03.jpg/1200px-Cat03.jpg'
image_data = requests.get(url).content

# Enroll facial data
result = FacialRecognitionService.enroll_facial_data(
    user=user,
    image_data=image_data,
    ip_address='127.0.0.1',
    device_info='Test Device'
)
print(result['success'])
```

### Test MFA

```python
from security import MFAService

# Enable MFA
result = MFAService.enable_mfa(user, method='password_otp')
if result['success']:
    print(f"Backup codes: {result['backup_codes']}")
    # Save backup codes!

# Check if MFA required
result = MFAService.initiate_mfa_verification(user)
print(f"Factors required: {result['required_factors']}")
```

### Test Role-Based Access

```python
from security import AccessControlService

# Assign role
AccessControlService.assign_role(user, 'admin')

# Check permissions
if AccessControlService.has_permission(user, 'add_payment'):
    print("User can add payments")
```

---

## Django Admin Interface

1. Start Django: `python manage.py runserver`
2. Go to http://localhost:8000/admin/
3. Login with admin account
4. Navigate to **Security** section to manage:
   - Security Settings
   - User Security Profiles
   - OTP Logs
   - Biometric Data
   - MFA Settings
   - Login Attempts
   - Audit Logs
   - Sessions

---

## Common Use Cases

### Use Case 1: User Login with OTP

```python
# Step 1: Authenticate password
result = AuthenticationService.authenticate_user(
    username='john_doe',
    password='password123',
    ip_address='192.168.1.1'
)

if result['requires_mfa']:
    # Step 2: Verify OTP
    otp_result = OTPService.verify_otp(result['user'], otp_code='123456')
    if otp_result['success']:
        # Step 3: Complete login
        AuthenticationService.complete_login(result['user'])
```

### Use Case 2: Register Biometric

```python
# User registers facial recognition
result = FacialRecognitionService.enroll_facial_data(user, image_data)
if result['success']:
    # Enable facial MFA
    MFAService.enable_mfa(user, method='password_facial')
```

### Use Case 3: Audit Trail Review

```python
from security import AuditLogger

# Get user's security report
report = AuditLogger.generate_security_report(user, days=30)
print(report)

# View login history
login_history = AuditLogger.get_login_history(user, limit=10)
for attempt in login_history:
    print(f"{attempt.attempted_at}: {attempt.ip_address}")
```

---

## Protecting Views with Decorators

```python
from django.shortcuts import render
from security.decorators import (
    require_permission,
    require_role,
    admin_only,
    audit_log_action,
    check_session_valid
)

# Require specific permission
@require_permission('edit_payment')
def edit_payment(request, payment_id):
    # User must have 'edit_payment' permission
    pass

# Require admin role
@admin_only
def admin_dashboard(request):
    # Only admins can access
    pass

# Require any role
@require_role('operator')
@check_session_valid
@audit_log_action('payment_edit', 'User edited payment')
def process_payment(request):
    # Process payment and auto-log action
    pass
```

---

## Configuration

Edit `config/settings.py` to customize:

```python
# Security settings
SECURITY_CONFIG = {
    'OTP_EXPIRY_MINUTES': 15,
    'MAX_LOGIN_ATTEMPTS': 5,
    'ACCOUNT_LOCKOUT_MINUTES': 30,
    'SESSION_TIMEOUT_MINUTES': 30,
}

# Email settings
EMAIL_HOST_USER = 'your-email@gmail.com'
EMAIL_HOST_PASSWORD = 'your-app-password'

# Encryption
ENCRYPTION_KEY = b'your-encryption-key'
```

---

## API Examples

### Create Django REST API Views

```python
# views.py
from rest_framework.decorators import api_view
from rest_framework.response import Response
from security import OTPService, AuthenticationService

@api_view(['POST'])
def login_view(request):
    """User login"""
    result = AuthenticationService.authenticate_user(
        username=request.data['username'],
        password=request.data['password'],
        ip_address=get_client_ip(request)
    )
    return Response(result)

@api_view(['POST'])
def verify_otp_view(request):
    """Verify OTP"""
    result = OTPService.verify_otp(
        user=request.user,
        otp_code=request.data['otp']
    )
    return Response(result)

@api_view(['POST'])
def send_otp_view(request):
    """Send OTP"""
    result = OTPService.send_otp(
        user=request.user,
        ip_address=get_client_ip(request)
    )
    return Response({'success': result['success']})
```

---

## File Structure

```
backend/
├── security/                          # NEW Security Module
│   ├── __init__.py                   # Package initialization
│   ├── models.py                     # Database models
│   ├── apps.py                       # Django app config
│   ├── admin.py                      # Django admin interface
│   ├── decorators.py                 # View decorators
│   ├── authentication.py             # Authentication service
│   ├── otp_service.py                # OTP service
│   ├── facial_recognition.py         # Facial recognition
│   ├── fingerprint_auth.py           # Fingerprint auth
│   ├── mfa_service.py                # MFA service
│   ├── encryption.py                 # Encryption utilities
│   ├── access_control.py             # RBAC service
│   ├── audit_logs.py                 # Audit logging
│   ├── security_settings.py          # Configuration
│   ├── migrations/                   # Database migrations
│   │   ├── __init__.py
│   │   └── 0001_initial.py           # Initial migration
│   └── tests.py                      # Unit tests (optional)
├── SECURITY_IMPLEMENTATION.md        # Comprehensive documentation
├── config/
│   └── settings.py                   # Updated with security config
├── requirements.txt                  # Updated with security deps
└── manage.py
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Email not sending | Check EMAIL_HOST_USER/PASSWORD in env variables |
| Face recognition not working | Install `pip install face-recognition dlib` |
| Import errors | Verify security package is in INSTALLED_APPS |
| Database errors | Run `python manage.py migrate security` |
| Permission denied | Check user role with `AccessControlService.get_user_role(user)` |

---

## Next Steps

1. ✅ Create login views that use `AuthenticationService`
2. ✅ Create OTP verification templates
3. ✅ Create biometric enrollment forms
4. ✅ Integrate with frontend React app
5. ✅ Configure email settings for your domain
6. ✅ Set up logging and monitoring
7. ✅ Enable HTTPS in production

---

## Support

For issues:
1. Check `logs/security.log` and `logs/audit.log`
2. Review models in Django admin
3. Check `AuditLog` model for error details
4. Enable DEBUG=True in settings for more details

---

**Congratulations! Your security system is ready to use! 🎉**

For detailed documentation, see: `SECURITY_IMPLEMENTATION.md`
