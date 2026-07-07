# Security Module Documentation

## Overview

The Security Module provides comprehensive authentication, authorization, and protection features for the Internet Payment Tracking system, including:

- **Email OTP Authentication** - One-time passwords sent via Gmail
- **Facial Recognition** - Biometric face verification
- **Fingerprint Authentication** - Biometric fingerprint verification
- **Multi-Factor Authentication (MFA)** - Combinations of authentication methods
- **Role-Based Access Control (RBAC)** - User authorization based on roles
- **Account Protection** - Account lockout, session timeout, inactivity detection
- **Encryption** - Secure storage of sensitive data
- **Audit Logging** - Complete security event tracking

---

## Installation & Setup

### 1. Install Dependencies

The security module requires additional Python packages. Install them:

```bash
pip install -r requirements.txt
```

Key packages:
- `face-recognition` - Facial recognition
- `opencv-python` - Image processing
- `cryptography` - Data encryption
- `dlib` - Facial feature detection
- `numpy`, `scipy` - Scientific computing

### 2. Add to Django Settings

The security app is already added to `INSTALLED_APPS` in `config/settings.py`:

```python
INSTALLED_APPS = [
    ...
    'security',
]
```

### 3. Configure Email Settings

For OTP via Gmail, update your environment variables or `settings.py`:

```python
# settings.py
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD')  # Use App Password, not Gmail password
```

**Gmail App Password Setup:**
1. Enable 2-Factor Authentication on your Google Account
2. Go to https://myaccount.google.com/apppasswords
3. Select "Mail" and "Windows Computer"
4. Copy the generated 16-character password
5. Use this as EMAIL_HOST_PASSWORD (without spaces)

### 4. Set Encryption Key

Generate and store an encryption key:

```python
# In terminal
from cryptography.fernet import Fernet
key = Fernet.generate_key()
print(key.decode())

# Then in environment or settings
ENCRYPTION_KEY = b'your-key-here'
```

### 5. Run Migrations

Create security database tables:

```bash
python manage.py migrate security
```

---

## Features & Usage

### 1. Email OTP Authentication

Send and verify one-time passwords via email.

#### Sending OTP

```python
from security import OTPService
from django.contrib.auth.models import User

user = User.objects.get(username='john_doe')
result = OTPService.send_otp(
    user=user,
    ip_address='192.168.1.1',
    user_agent='Mozilla/5.0...',
    expiry_minutes=15
)

if result['success']:
    print(f"OTP sent to {user.email}")
else:
    print(f"Error: {result['error']}")
```

#### Verifying OTP

```python
result = OTPService.verify_otp(
    user=user,
    otp_code='123456',
    ip_address='192.168.1.1',
    user_agent='Mozilla/5.0...'
)

if result['success']:
    print("OTP verified successfully!")
else:
    print(f"Verification failed: {result['error']}")
```

#### Checking OTP Expiry

```python
expiry_info = OTPService.get_otp_expiry_time(user)
print(f"Minutes remaining: {expiry_info['minutes']}")
print(f"Seconds remaining: {expiry_info['seconds']}")
```

---

### 2. Facial Recognition

Enroll and verify user facial data for secure authentication.

#### Enrolling Facial Data

```python
from security import FacialRecognitionService

# Image data from file upload
with open('user_face.jpg', 'rb') as f:
    image_data = f.read()

result = FacialRecognitionService.enroll_facial_data(
    user=user,
    image_data=image_data,
    ip_address='192.168.1.1',
    device_info='iPhone 14'
)

if result['success']:
    print(f"Facial data enrolled! Quality: {result['biometric_data'].enrollment_quality_score}")
else:
    print(f"Enrollment failed: {result['error']}")
```

**Requirements:**
- Single face per image
- Good lighting and clear facial features
- Minimum quality score: 0.8

#### Verifying Face

```python
with open('verify_face.jpg', 'rb') as f:
    image_data = f.read()

result = FacialRecognitionService.verify_face(
    user=user,
    image_data=image_data,
    ip_address='192.168.1.1',
    device_info='iPhone 14',
    reason='login'
)

if result['success']:
    print(f"Face verified! Confidence: {result['match_confidence']:.2f}%")
else:
    print(f"Verification failed: {result['error']}")
```

#### Checking Enrollment Status

```python
if FacialRecognitionService.is_facial_enrolled(user):
    print("User has facial data enrolled")
```

---

### 3. Fingerprint Authentication

Enroll and verify fingerprints for biometric authentication.

#### Enrolling Fingerprint

```python
from security import FingerprintAuthService

# Fingerprint data from scanner or API
fingerprint_data = {
    'minutiae': [...],
    'ridge_pattern': 'whorl',
    ...
}

result = FingerprintAuthService.enroll_fingerprint(
    user=user,
    fingerprint_template=fingerprint_data,
    fingerprint_position='thumb_r',
    ip_address='192.168.1.1',
    device_info='Fingerprint Scanner'
)

if result['success']:
    print(f"Fingerprint enrolled! Quality: {result['biometric_data'].enrollment_quality_score}")
else:
    print(f"Enrollment failed: {result['error']}")
```

#### Verifying Fingerprint

```python
result = FingerprintAuthService.verify_fingerprint(
    user=user,
    fingerprint_template=fingerprint_data,
    ip_address='192.168.1.1',
    device_info='Fingerprint Scanner',
    reason='login'
)

if result['success']:
    print(f"Fingerprint verified! Confidence: {result['match_confidence']:.2f}%")
else:
    print(f"Verification failed: {result['error']}")
```

---

### 4. Multi-Factor Authentication (MFA)

Combine multiple authentication factors for enhanced security.

#### Supported MFA Methods

1. **Password + OTP** - Password and one-time code
2. **Password + Facial** - Password and facial recognition
3. **Password + Fingerprint** - Password and fingerprint
4. **Password + OTP + Facial** - All three factors
5. **Password + OTP + Fingerprint** - All three factors

#### Enabling MFA

```python
from security import MFAService

result = MFAService.enable_mfa(
    user=user,
    method='password_otp'
)

if result['success']:
    print(f"MFA enabled with method: password_otp")
    print(f"Backup codes: {result['backup_codes']}")
    # Store backup codes securely!
else:
    print(f"Error: {result['error']}")
```

#### Initiating MFA Verification

```python
result = MFAService.initiate_mfa_verification(
    user=user,
    ip_address='192.168.1.1',
    device_info='Chrome on Windows',
    reason='login'
)

if result['success']:
    print(f"Required factors: {result['required_factors']}")
    # required_factors = ['password', 'otp']
```

#### Verifying MFA Factors

```python
factors_data = {
    'otp': '123456',
    'facial': facial_image_bytes,
    'fingerprint': fingerprint_data
}

result = MFAService.verify_mfa_factors(
    user=user,
    factors_data=factors_data,
    ip_address='192.168.1.1',
    device_info='Chrome on Windows'
)

if result['success']:
    print(f"All factors verified! Verified: {result['verified_factors']}")
else:
    print(f"Failed factors: {result['failed_factors']}")
```

#### Using Backup Codes

```python
result = MFAService.verify_backup_code(
    user=user,
    code='a1b2c3d4'
)

if result['success']:
    print("Backup code verified! Account recovered.")
```

---

### 5. User Authentication

Handle complete login flow with security checks.

#### Authenticating User

```python
from security import AuthenticationService

result = AuthenticationService.authenticate_user(
    username='john_doe',
    password='secure_password',
    ip_address='192.168.1.1',
    user_agent='Mozilla/5.0...',
    device_info='Chrome on Windows'
)

if result['success']:
    user = result['user']
    if result['requires_mfa']:
        # Redirect to MFA verification page
        print("MFA required")
    else:
        # Proceed with login
        AuthenticationService.complete_login(
            user=user,
            ip_address='192.168.1.1',
            user_agent='Mozilla/5.0...',
            device_info='Chrome on Windows'
        )
else:
    print(f"Authentication failed: {result['error']}")
```

#### Account Lockout

Accounts are automatically locked after 5 failed login attempts (configurable).

```python
# Check if account is locked
if user.security_profile.is_account_locked():
    print("Account is locked")

# Unlock account (admin only)
AuthenticationService.unlock_account(user)
```

#### Logout

```python
AuthenticationService.logout_user(user, session_key='session_123')
```

---

### 6. Role-Based Access Control (RBAC)

Control access based on user roles.

#### Available Roles

- **Admin** - Full system access
- **Operator** - Manage payments and tickets
- **Client** - View own data
- **Viewer** - Read-only access

#### Assigning Roles

```python
from security import AccessControlService

result = AccessControlService.assign_role(user, 'operator')
if result['success']:
    print(f"Role assigned: {result['message']}")
```

#### Checking Permissions

```python
if AccessControlService.has_permission(user, 'add_payment'):
    print("User can add payments")

if AccessControlService.has_role(user, 'admin'):
    print("User is admin")
```

#### Protecting Views

```python
from django.contrib.auth.decorators import login_required
from security.decorators import require_permission

@login_required
@require_permission('edit_payment')
def edit_payment(request, payment_id):
    # Only accessible to users with 'edit_payment' permission
    pass
```

---

### 7. Encryption

Encrypt sensitive user data.

#### Encrypting Data

```python
from security import EncryptionService

# Encrypt email
encrypted_email = EncryptionService.encrypt_email('user@example.com')

# Decrypt email
email = EncryptionService.decrypt_email(encrypted_email)

# Encrypt other data
encrypted = EncryptionService.encrypt_data('sensitive_data')
decrypted = EncryptionService.decrypt_data(encrypted)
```

#### Password Hashing

```python
# Hash password (use Django's built-in)
hashed = EncryptionService.hash_password('password123')

# Verify password
if EncryptionService.verify_password('password123', hashed):
    print("Password matches!")
```

---

### 8. Audit Logging

Track all security events for compliance and investigation.

#### Manual Audit Logging

```python
from security import AuditLogger

AuditLogger.log_action(
    user=user,
    action_type='login',
    description='User login successful',
    ip_address='192.168.1.1',
    user_agent='Mozilla/5.0...',
    device_info='Chrome',
    status='success'
)
```

#### Viewing Audit Trail

```python
# Get user's audit trail for last 30 days
audit_trail = AuditLogger.get_user_audit_trail(user, days=30)
for log in audit_trail:
    print(f"{log.timestamp} - {log.action_type}: {log.description}")

# Get login history
login_history = AuditLogger.get_login_history(user, limit=10)
for attempt in login_history:
    print(f"{attempt.attempted_at} - {attempt.ip_address}")

# Get failed login attempts in last 24 hours
failed_logins = AuditLogger.get_failed_login_attempts(user, hours=24)
```

#### Security Report

```python
report = AuditLogger.generate_security_report(user, days=30)
print(f"Risk Level: {report['risk_assessment']}")
print(f"Total Logins: {report['login_statistics']['total_successful_logins']}")
print(f"Failed Logins: {report['login_statistics']['total_failed_logins']}")
```

---

## Database Models

### SecuritySettings
Global security configuration:
- OTP expiry time
- Maximum login attempts
- Account lockout duration
- Session timeout
- MFA requirement

### UserSecurityProfile
Per-user security settings:
- Role assignment
- Biometric enrollment status
- MFA configuration
- Account lockout status
- Password expiry tracking
- Session management
- Last activity tracking

### OTPLog
OTP generation and verification records:
- OTP code and recipient email
- Creation and expiry time
- Verification status and attempts
- Request metadata (IP, user agent)

### BiometricData
Enrolled biometric templates:
- User's facial or fingerprint template
- Template hash for comparison
- Enrollment quality score
- Last verification timestamp
- Enrollment metadata

### MFASettings
Multi-factor authentication configuration:
- Enabled status
- Authentication method
- Backup codes for recovery
- Verification history

### LoginAttempt
Login attempt tracking:
- Successful/failed status
- IP address and user agent
- Device information
- Attempt timestamp

### BiometricVerification
Biometric verification attempts:
- Verification type (facial/fingerprint)
- Result and match confidence
- Request metadata

### AuditLog
Comprehensive security event log:
- Action type and description
- User and affected user
- IP address and device info
- Timestamp and status
- Error details for failed actions

### SessionManagement
Active session tracking:
- Session key and user
- IP address and device info
- Creation, expiry, and last activity time
- Active status for session validation

---

## Security Best Practices

### 1. Password Policy
- Minimum 12 characters
- Require uppercase, lowercase, digits, and special characters
- Expire after 90 days
- Maintain history of 5 previous passwords

### 2. Account Protection
- Lock account after 5 failed login attempts
- Lock for 30 minutes
- Require password reset after unlock
- Monitor for suspicious activity

### 3. Session Management
- 30-minute session timeout
- Inactivity timeout
- Force secure cookies (HTTPS only)
- HttpOnly flag to prevent JavaScript access
- SameSite=Strict to prevent CSRF

### 4. Encryption
- Use Fernet symmetric encryption for sensitive data
- Store encryption key securely (environment variable)
- Never hardcode encryption keys
- Rotate keys annually

### 5. Audit Logging
- Log all authentication attempts
- Log biometric verification results
- Log account lockouts and unlocks
- Retain logs for 90 days minimum
- Review logs regularly for anomalies

### 6. MFA
- Enable for all administrative users
- Recommend for regular users
- Support multiple authentication methods
- Provide backup codes for account recovery

### 7. IP Tracking
- Track IP address of login attempts
- Alert on new IP addresses
- Implement geographic validation if needed
- Maintain IP whitelist for sensitive operations

---

## Configuration

Edit `security/security_settings.py` to customize security parameters:

```python
SECURITY_SETTINGS = {
    'OTP': {
        'LENGTH': 6,
        'EXPIRY_MINUTES': 15,
        'MAX_ATTEMPTS': 5,
    },
    'LOGIN': {
        'MAX_FAILED_ATTEMPTS': 5,
        'LOCKOUT_DURATION_MINUTES': 30,
        'SESSION_TIMEOUT_MINUTES': 30,
    },
    'PASSWORD': {
        'MIN_LENGTH': 12,
        'REQUIRE_UPPERCASE': True,
        'REQUIRE_LOWERCASE': True,
        'REQUIRE_DIGITS': True,
        'REQUIRE_SPECIAL_CHARS': True,
    },
    ...
}
```

---

## Admin Interface

Manage security settings from Django Admin:

1. Go to `/admin/`
2. Navigate to **Security** section
3. Manage:
   - Security Settings
   - User Security Profiles
   - OTP Logs
   - Biometric Data
   - MFA Settings
   - Login Attempts
   - Audit Logs
   - Active Sessions

---

## Troubleshooting

### OTP Not Sending
- Check EMAIL_HOST_USER and EMAIL_HOST_PASSWORD
- Verify Gmail App Password is correct
- Check email logs: `LoginAttempt` and `AuditLog` models

### Facial Recognition Not Working
- Install `face_recognition` and dependencies: `pip install face-recognition dlib`
- Check image quality (must be clear and well-lit)
- Ensure face is fully visible
- Try with different image format

### Fingerprint Enrollment Failing
- Provide clear fingerprint image
- Ensure minimum minutiae points detected
- Try different scanner or API

### Account Locked
- Admin can unlock via Django admin
- Automatic unlock after lockout period
- Check `UserSecurityProfile.locked_until`

---

## API Endpoints (Example)

```
POST   /api/auth/login/          - Login with credentials
POST   /api/auth/otp/send/       - Send OTP
POST   /api/auth/otp/verify/     - Verify OTP
POST   /api/auth/facial/enroll/  - Enroll facial data
POST   /api/auth/facial/verify/  - Verify face
POST   /api/auth/mfa/enable/     - Enable MFA
POST   /api/auth/mfa/verify/     - Verify MFA factors
POST   /api/auth/logout/         - Logout
GET    /api/audit-logs/          - View audit trail
```

---

## Support & Issues

For issues or questions:
1. Check audit logs for error details
2. Enable debug logging: `LOGGING` configuration in settings
3. Review security documentation
4. Contact system administrator

---

## Version History

**v1.0.0** (Current)
- Email OTP Authentication
- Facial Recognition
- Fingerprint Authentication
- Multi-Factor Authentication
- Role-Based Access Control
- Complete Audit Logging
- Account Protection Features
- Encryption Service

---

**Documentation Last Updated:** 2026-06-22
**Module Version:** 1.0.0
