from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
import json


class SecuritySettings(models.Model):
    """Global security configuration"""
    OTP_EXPIRY_MINUTES = 5
    MAX_LOGIN_ATTEMPTS = 5
    LOCKOUT_DURATION_MINUTES = 30
    SESSION_TIMEOUT_MINUTES = 30
    
    otp_expiry_minutes = models.IntegerField(default=OTP_EXPIRY_MINUTES)
    max_login_attempts = models.IntegerField(default=MAX_LOGIN_ATTEMPTS)
    lockout_duration_minutes = models.IntegerField(default=LOCKOUT_DURATION_MINUTES)
    session_timeout_minutes = models.IntegerField(default=SESSION_TIMEOUT_MINUTES)
    require_mfa = models.BooleanField(default=False)
    
    class Meta:
        verbose_name_plural = "Security Settings"
    
    def __str__(self):
        return "System Security Settings"


class UserSecurityProfile(models.Model):
    """User security preferences and status"""
    ROLE_CHOICES = [
        ('admin', 'Administrator'),
        ('operator', 'Operator'),
        ('client', 'Client'),
        ('viewer', 'Viewer'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='security_profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='client')
    
    # Biometric enrollment status
    facial_data_enrolled = models.BooleanField(default=False)
    fingerprint_enrolled = models.BooleanField(default=False)
    phone_number = models.CharField(max_length=20, blank=True, default='')
    
    # MFA preferences
    mfa_enabled = models.BooleanField(default=False)
    mfa_method = models.CharField(max_length=100, default='')  # e.g., "password+otp"
    
    # Account security
    account_locked = models.BooleanField(default=False)
    locked_until = models.DateTimeField(null=True, blank=True)
    failed_login_attempts = models.IntegerField(default=0)
    
    # Password security
    password_changed_at = models.DateTimeField(auto_now_add=True)
    password_expiry_days = models.IntegerField(default=90)
    force_password_change = models.BooleanField(default=False)
    
    # Session management
    last_login_ip = models.CharField(max_length=45, blank=True)  # IPv4 or IPv6
    last_login_timestamp = models.DateTimeField(null=True, blank=True)
    active_session_id = models.CharField(max_length=255, blank=True)
    
    # Activity tracking
    last_activity = models.DateTimeField(auto_now=True)
    inactive_lockout_enabled = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name_plural = "User Security Profiles"
    
    def __str__(self):
        return f"Security Profile: {self.user.username}"
    
    def is_account_locked(self):
        """Check if account is currently locked"""
        if not self.account_locked:
            return False
        if self.locked_until and self.locked_until > timezone.now():
            return True
        # Unlock if lockout period expired
        self.account_locked = False
        self.locked_until = None
        self.failed_login_attempts = 0
        self.save()
        return False
    
    def is_password_expired(self):
        """Check if password has expired"""
        expiry_date = self.password_changed_at + timedelta(days=self.password_expiry_days)
        return timezone.now() > expiry_date
    
    def is_session_expired(self, session_timeout_minutes=30):
        """Check if session has timed out due to inactivity"""
        inactivity_threshold = timezone.now() - timedelta(minutes=session_timeout_minutes)
        return self.last_activity < inactivity_threshold


class OTPLog(models.Model):
    """OTP storage and validation"""
    OTP_STATUS = [
        ('active', 'Active'),
        ('used', 'Used'),
        ('expired', 'Expired'),
        ('invalid', 'Invalid'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='otp_logs')
    otp_code = models.CharField(max_length=6)
    email_sent_to = models.EmailField()
    status = models.CharField(max_length=20, choices=OTP_STATUS, default='active')
    
    # OTP timing
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    verified_at = models.DateTimeField(null=True, blank=True)
    
    # Attempt tracking
    verification_attempts = models.IntegerField(default=0)
    max_attempts = models.IntegerField(default=5)
    
    # Metadata
    ip_address = models.CharField(max_length=45, blank=True)
    user_agent = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"OTP for {self.user.username} - {self.status}"
    
    def is_valid(self):
        """Check if OTP is still valid"""
        if self.status != 'active':
            return False
        if timezone.now() > self.expires_at:
            self.status = 'expired'
            self.save()
            return False
        if self.verification_attempts >= self.max_attempts:
            self.status = 'invalid'
            self.save()
            return False
        return True
    
    def increment_attempts(self):
        """Track verification attempts"""
        self.verification_attempts += 1
        self.save()
    
    def mark_as_used(self):
        """Mark OTP as successfully used"""
        self.status = 'used'
        self.verified_at = timezone.now()
        self.save()


class BiometricData(models.Model):
    """Store facial recognition and fingerprint templates"""
    BIOMETRIC_TYPE = [
        ('facial', 'Facial Recognition'),
        ('fingerprint', 'Fingerprint'),
        ('mobile_passkey', 'Mobile Passkey'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='biometric_data')
    biometric_type = models.CharField(max_length=20, choices=BIOMETRIC_TYPE)
    
    # Encoded biometric template (JSON format for facial landmarks, or hex for fingerprint)
    template_data = models.TextField()
    template_hash = models.CharField(max_length=255, db_index=True)
    sample_image_path = models.CharField(max_length=500, blank=True, default='')
    
    # Enrollment details
    enrolled_at = models.DateTimeField(auto_now_add=True)
    enrolled_from_ip = models.CharField(max_length=45, blank=True)
    enrollment_device = models.CharField(max_length=255, blank=True)
    
    # Quality metrics
    enrollment_quality_score = models.FloatField(default=0.0)  # 0-100
    enrollment_confidence = models.FloatField(default=0.0)     # 0-100
    
    # Status
    is_active = models.BooleanField(default=True)
    last_verified_at = models.DateTimeField(null=True, blank=True)
    
    # Update tracking
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        constraints = []
    
    def __str__(self):
        return f"{self.user.username} - {self.biometric_type}"


class MFASettings(models.Model):
    """Multi-Factor Authentication configuration per user"""
    MFA_METHODS = [
        ('password_otp', 'Password + OTP'),
        ('password_facial', 'Password + Facial Recognition'),
        ('password_fingerprint', 'Password + Fingerprint'),
        ('password_otp_facial', 'Password + OTP + Facial'),
        ('password_otp_fingerprint', 'Password + OTP + Fingerprint'),
        ('password_otp_facial_fingerprint', 'Password + OTP + Facial + Fingerprint'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='mfa_settings')
    is_enabled = models.BooleanField(default=False)
    method = models.CharField(max_length=50, choices=MFA_METHODS, default='password_otp')
    
    # Backup codes for account recovery
    backup_codes = models.TextField(blank=True)  # JSON list of codes
    backup_codes_used = models.TextField(blank=True)  # JSON list of used codes
    
    # Settings
    require_on_every_login = models.BooleanField(default=False)
    require_on_suspicious_login = models.BooleanField(default=True)
    require_biometric_for_sensitive_actions = models.BooleanField(default=False)
    allow_otp_login = models.BooleanField(default=True)
    allow_facial_login = models.BooleanField(default=True)
    allow_fingerprint_login = models.BooleanField(default=True)
    
    # Metadata
    enabled_at = models.DateTimeField(null=True, blank=True)
    last_verified_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name_plural = "MFA Settings"
    
    def __str__(self):
        return f"MFA Settings: {self.user.username}"
    
    def get_backup_codes(self):
        """Parse backup codes from JSON"""
        if self.backup_codes:
            return json.loads(self.backup_codes)
        return []
    
    def get_used_codes(self):
        """Parse used codes from JSON"""
        if self.backup_codes_used:
            return json.loads(self.backup_codes_used)
        return []
    
    def mark_backup_code_as_used(self, code):
        """Mark a backup code as used"""
        used_codes = self.get_used_codes()
        if code not in used_codes:
            used_codes.append(code)
            self.backup_codes_used = json.dumps(used_codes)
            self.save()


class LoginAttempt(models.Model):
    """Track login attempts for security and analytics"""
    STATUS_CHOICES = [
        ('success', 'Successful'),
        ('failed', 'Failed'),
        ('locked', 'Account Locked'),
        ('otp_required', 'OTP Required'),
        ('biometric_required', 'Biometric Required'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='login_attempts', null=True, blank=True)
    username = models.CharField(max_length=150)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    
    # Request metadata
    ip_address = models.CharField(max_length=45)
    user_agent = models.TextField()
    device_info = models.CharField(max_length=255, blank=True)
    login_method = models.CharField(max_length=50, blank=True, default='')
    
    # Timestamps
    attempted_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Additional info
    reason = models.TextField(blank=True)
    geolocation = models.CharField(max_length=255, blank=True)
    
    class Meta:
        ordering = ['-attempted_at']
    
    def __str__(self):
        return f"{self.username} - {self.status} ({self.attempted_at})"


class BiometricVerification(models.Model):
    """Log all facial recognition and fingerprint verification attempts"""
    VERIFICATION_TYPE = [
        ('facial', 'Facial Recognition'),
        ('fingerprint', 'Fingerprint'),
    ]
    
    RESULT_CHOICES = [
        ('success', 'Successful'),
        ('failed', 'Failed'),
        ('quality_low', 'Quality Too Low'),
        ('not_matched', 'No Match'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='biometric_verifications')
    verification_type = models.CharField(max_length=20, choices=VERIFICATION_TYPE)
    result = models.CharField(max_length=20, choices=RESULT_CHOICES)
    
    # Verification data
    match_confidence = models.FloatField(default=0.0)  # 0-100
    match_threshold = models.FloatField(default=0.95)   # 0-1
    
    # Timing and metadata
    attempted_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.CharField(max_length=45, blank=True)
    device_info = models.CharField(max_length=255, blank=True)
    
    # Additional context
    session_id = models.CharField(max_length=255, blank=True)
    reason = models.CharField(max_length=100, blank=True)  # login, payment_confirmation, etc.
    
    class Meta:
        ordering = ['-attempted_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.verification_type} - {self.result}"


class AuditLog(models.Model):
    """Comprehensive audit trail for all security-related actions"""
    ACTION_TYPES = [
        ('login', 'Login'),
        ('logout', 'Logout'),
        ('otp_request', 'OTP Requested'),
        ('otp_verify', 'OTP Verification'),
        ('facial_enroll', 'Facial Enrollment'),
        ('facial_verify', 'Facial Verification'),
        ('fingerprint_enroll', 'Fingerprint Enrollment'),
        ('fingerprint_verify', 'Fingerprint Verification'),
        ('mfa_enable', 'MFA Enabled'),
        ('mfa_disable', 'MFA Disabled'),
        ('password_change', 'Password Changed'),
        ('account_lockout', 'Account Locked'),
        ('account_unlock', 'Account Unlocked'),
        ('permission_change', 'Permission Changed'),
        ('role_change', 'Role Changed'),
        ('admin_action', 'Administrative Action'),
        ('security_event', 'Security Event'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='audit_logs', null=True, blank=True)
    action_type = models.CharField(max_length=50, choices=ACTION_TYPES)
    description = models.TextField()
    
    # Request context
    ip_address = models.CharField(max_length=45)
    user_agent = models.TextField(blank=True)
    device_info = models.CharField(max_length=255, blank=True)
    
    # Timestamp
    timestamp = models.DateTimeField(auto_now_add=True)
    
    # Result and status
    status = models.CharField(max_length=20, default='success')  # success, failed, warning
    error_message = models.TextField(blank=True)
    
    # Additional metadata
    session_id = models.CharField(max_length=255, blank=True)
    related_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='related_audit_logs')
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', '-timestamp']),
            models.Index(fields=['action_type', '-timestamp']),
        ]
    
    def __str__(self):
        return f"{self.action_type} - {self.user} ({self.timestamp})"


class SessionManagement(models.Model):
    """Manage user sessions for security"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sessions')
    session_key = models.CharField(max_length=255, unique=True)
    ip_address = models.CharField(max_length=45)
    user_agent = models.TextField()
    device_info = models.CharField(max_length=255, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField()
    
    # Status
    is_active = models.BooleanField(default=True)
    force_logout = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Session: {self.user.username} - {self.session_key[:20]}"
    
    def is_expired(self):
        """Check if session has expired"""
        return timezone.now() > self.expires_at or not self.is_active
    
    def is_inactive_timeout(self, timeout_minutes=30):
        """Check if session has timed out due to inactivity"""
        inactivity_threshold = timezone.now() - timedelta(minutes=timeout_minutes)
        return self.last_activity < inactivity_threshold
