"""
Security Module - Comprehensive security and authentication system
Includes OTP, Facial Recognition, Fingerprint Authentication, MFA, and Audit Logging
"""

__version__ = '1.0.0'

# Lazy imports to avoid circular dependencies
def __getattr__(name):
    """Lazy load modules on demand"""
    if name == 'SecuritySettings':
        from .models import SecuritySettings
        return SecuritySettings
    elif name == 'UserSecurityProfile':
        from .models import UserSecurityProfile
        return UserSecurityProfile
    elif name == 'OTPLog':
        from .models import OTPLog
        return OTPLog
    elif name == 'BiometricData':
        from .models import BiometricData
        return BiometricData
    elif name == 'MFASettings':
        from .models import MFASettings
        return MFASettings
    elif name == 'LoginAttempt':
        from .models import LoginAttempt
        return LoginAttempt
    elif name == 'BiometricVerification':
        from .models import BiometricVerification
        return BiometricVerification
    elif name == 'AuditLog':
        from .models import AuditLog
        return AuditLog
    elif name == 'SessionManagement':
        from .models import SessionManagement
        return SessionManagement
    elif name == 'OTPService':
        from .otp_service import OTPService
        return OTPService
    elif name == 'FacialRecognitionService':
        from .facial_recognition import FacialRecognitionService
        return FacialRecognitionService
    elif name == 'FingerprintAuthService':
        from .fingerprint_auth import FingerprintAuthService
        return FingerprintAuthService
    elif name == 'MFAService':
        from .mfa_service import MFAService
        return MFAService
    elif name == 'AuthenticationService':
        from .authentication import AuthenticationService
        return AuthenticationService
    elif name == 'EncryptionService':
        from .encryption import EncryptionService
        return EncryptionService
    elif name == 'AccessControlService':
        from .access_control import AccessControlService
        return AccessControlService
    elif name == 'AuditLogger':
        from .audit_logs import AuditLogger
        return AuditLogger
    else:
        raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


__all__ = [
    # Models
    'SecuritySettings',
    'UserSecurityProfile',
    'OTPLog',
    'BiometricData',
    'MFASettings',
    'LoginAttempt',
    'BiometricVerification',
    'AuditLog',
    'SessionManagement',
    # Services
    'OTPService',
    'FacialRecognitionService',
    'FingerprintAuthService',
    'MFAService',
    'AuthenticationService',
    'EncryptionService',
    'AccessControlService',
    'AuditLogger',
]

