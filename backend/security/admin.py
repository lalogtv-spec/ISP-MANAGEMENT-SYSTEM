from django.contrib import admin
from django.core.mail import send_mail
from django.conf import settings
from django.utils.html import format_html
from .models import (
    SecuritySettings,
    UserSecurityProfile,
    OTPLog,
    BiometricData,
    MFASettings,
    LoginAttempt,
    BiometricVerification,
    AuditLog,
    SessionManagement,
)


@admin.register(SecuritySettings)
class SecuritySettingsAdmin(admin.ModelAdmin):
    list_display = ('otp_expiry_minutes', 'max_login_attempts', 'lockout_duration_minutes', 'require_mfa')
    fieldsets = (
        ('OTP Configuration', {
            'fields': ('otp_expiry_minutes',)
        }),
        ('Login Security', {
            'fields': ('max_login_attempts', 'lockout_duration_minutes', 'session_timeout_minutes')
        }),
        ('MFA', {
            'fields': ('require_mfa',)
        }),
    )


@admin.register(UserSecurityProfile)
class UserSecurityProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'phone_number', 'account_locked_status', 'biometric_status', 'mfa_enabled', 'facial_enrolled', 'fingerprint_enrolled')
    list_filter = ('role', 'account_locked', 'mfa_enabled', 'facial_data_enrolled', 'fingerprint_enrolled')
    search_fields = ('user__username', 'user__email')
    readonly_fields = ('created_at', 'updated_at', 'last_activity')
    actions = ('send_biometric_reminders',)
    
    fieldsets = (
        ('User', {
            'fields': ('user', 'role', 'phone_number')
        }),
        ('Biometric Enrollment', {
            'fields': ('facial_data_enrolled', 'fingerprint_enrolled')
        }),
        ('MFA', {
            'fields': ('mfa_enabled', 'mfa_method')
        }),
        ('Account Security', {
            'fields': ('account_locked', 'locked_until', 'failed_login_attempts')
        }),
        ('Password Security', {
            'fields': ('password_changed_at', 'password_expiry_days', 'force_password_change')
        }),
        ('Session Information', {
            'fields': ('last_login_ip', 'last_login_timestamp', 'active_session_id', 'last_activity')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def account_locked_status(self, obj):
        if obj.account_locked:
            return format_html('<span style="color: red;">🔒 LOCKED</span>')
        return format_html('<span style="color: green;">🔓 Active</span>')
    account_locked_status.short_description = 'Account Status'
    
    def facial_enrolled(self, obj):
        return '✓' if obj.facial_data_enrolled else '✗'
    facial_enrolled.short_description = 'Facial'
    
    def fingerprint_enrolled(self, obj):
        return '✓' if obj.fingerprint_enrolled else '✗'
    fingerprint_enrolled.short_description = 'Fingerprint'

    def biometric_status(self, obj):
        face = obj.facial_data_enrolled
        fingerprint = obj.fingerprint_enrolled
        if face and fingerprint:
            return format_html('<span style="color: #10b981; font-weight: 700;">FULLY REGISTERED</span>')
        if face or fingerprint:
            return format_html('<span style="color: #f59e0b; font-weight: 700;">PARTIALLY REGISTERED</span>')
        return format_html('<span style="color: #ef4444; font-weight: 700;">BIOMETRICS NOT SET UP</span>')
    biometric_status.short_description = 'Biometric Status'

    @admin.action(description='Send biometric enrollment reminder')
    def send_biometric_reminders(self, request, queryset):
        sent = 0
        for profile in queryset:
            if profile.facial_data_enrolled and profile.fingerprint_enrolled:
                continue
            if not profile.user.email:
                continue
            try:
                send_mail(
                    subject='Biometric enrollment reminder',
                    message=(
                        f'Hello {profile.user.get_full_name() or profile.user.username},\n\n'
                        'Your account can use fingerprint and facial recognition for extra security. '
                        'Please visit your Security & Biometrics settings to complete registration.'
                    ),
                    from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', None),
                    recipient_list=[profile.user.email],
                    fail_silently=False,
                )
                sent += 1
            except Exception:
                continue
        self.message_user(request, f'Sent biometric reminders to {sent} user(s).')


@admin.register(OTPLog)
class OTPLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'email_sent_to', 'status_badge', 'created_at', 'expires_at', 'verification_attempts')
    list_filter = ('status', 'created_at', 'expires_at')
    search_fields = ('user__username', 'email_sent_to')
    readonly_fields = ('otp_code', 'user', 'email_sent_to', 'created_at', 'expires_at', 'verified_at')
    
    def status_badge(self, obj):
        colors = {'active': 'green', 'used': 'blue', 'expired': 'gray', 'invalid': 'red'}
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 5px 10px; border-radius: 3px;">{}</span>',
            color,
            obj.status.upper()
        )
    status_badge.short_description = 'Status'


@admin.register(BiometricData)
class BiometricDataAdmin(admin.ModelAdmin):
    list_display = ('user', 'biometric_type', 'is_active', 'enrollment_quality_score', 'enrolled_at')
    list_filter = ('biometric_type', 'is_active', 'enrolled_at')
    search_fields = ('user__username',)
    readonly_fields = ('template_hash', 'enrolled_at', 'created_at', 'updated_at', 'last_verified_at')
    
    fieldsets = (
        ('User Information', {
            'fields': ('user', 'biometric_type', 'is_active')
        }),
        ('Template Information', {
            'fields': ('template_data', 'template_hash')
        }),
        ('Quality Metrics', {
            'fields': ('enrollment_quality_score', 'enrollment_confidence')
        }),
        ('Enrollment Details', {
            'fields': ('enrolled_from_ip', 'enrollment_device', 'enrolled_at')
        }),
        ('Verification', {
            'fields': ('last_verified_at',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(MFASettings)
class MFASettingsAdmin(admin.ModelAdmin):
    list_display = ('user', 'is_enabled', 'method', 'enabled_at', 'require_biometric_for_sensitive_actions')
    list_filter = ('is_enabled', 'method', 'require_on_every_login', 'require_biometric_for_sensitive_actions', 'allow_otp_login')
    search_fields = ('user__username',)
    readonly_fields = ('enabled_at', 'last_verified_at')
    
    fieldsets = (
        ('User', {
            'fields': ('user',)
        }),
        ('MFA Configuration', {
            'fields': ('is_enabled', 'method')
        }),
        ('MFA Settings', {
            'fields': (
                'require_on_every_login',
                'require_on_suspicious_login',
                'require_biometric_for_sensitive_actions',
                'allow_otp_login',
            )
        }),
        ('Backup Codes', {
            'fields': ('backup_codes', 'backup_codes_used')
        }),
        ('Verification', {
            'fields': ('enabled_at', 'last_verified_at')
        }),
    )


@admin.register(LoginAttempt)
class LoginAttemptAdmin(admin.ModelAdmin):
    list_display = ('username', 'user', 'status_badge', 'ip_address', 'attempted_at')
    list_filter = ('status', 'attempted_at')
    search_fields = ('username', 'user__username', 'ip_address')
    readonly_fields = ('username', 'user', 'status', 'ip_address', 'user_agent', 'attempted_at', 'completed_at')
    
    def status_badge(self, obj):
        colors = {'success': 'green', 'failed': 'red', 'locked': 'orange', 'otp_required': 'blue', 'biometric_required': 'purple'}
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 5px 10px; border-radius: 3px;">{}</span>',
            color,
            obj.status.replace('_', ' ').upper()
        )
    status_badge.short_description = 'Status'


@admin.register(BiometricVerification)
class BiometricVerificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'verification_type', 'result_badge', 'match_confidence', 'attempted_at')
    list_filter = ('verification_type', 'result', 'attempted_at')
    search_fields = ('user__username',)
    readonly_fields = ('user', 'verification_type', 'result', 'attempted_at')
    
    def result_badge(self, obj):
        colors = {'success': 'green', 'failed': 'red', 'quality_low': 'orange', 'not_matched': 'red'}
        color = colors.get(obj.result, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 5px 10px; border-radius: 3px;">{}</span>',
            color,
            obj.result.replace('_', ' ').upper()
        )
    result_badge.short_description = 'Result'


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'action_type', 'status_badge', 'timestamp', 'ip_address')
    list_filter = ('action_type', 'status', 'timestamp')
    search_fields = ('user__username', 'description', 'ip_address')
    readonly_fields = ('user', 'action_type', 'description', 'ip_address', 'timestamp')
    
    fieldsets = (
        ('Action', {
            'fields': ('user', 'action_type', 'description', 'status')
        }),
        ('Request Information', {
            'fields': ('ip_address', 'user_agent', 'device_info')
        }),
        ('Session', {
            'fields': ('session_id', 'related_user')
        }),
        ('Error Information', {
            'fields': ('error_message',),
            'classes': ('collapse',)
        }),
        ('Timestamp', {
            'fields': ('timestamp',)
        }),
    )
    
    def status_badge(self, obj):
        colors = {'success': 'green', 'failed': 'red', 'warning': 'orange'}
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 5px 10px; border-radius: 3px;">{}</span>',
            color,
            obj.status.upper()
        )
    status_badge.short_description = 'Status'


@admin.register(SessionManagement)
class SessionManagementAdmin(admin.ModelAdmin):
    list_display = ('user', 'session_status', 'ip_address', 'created_at', 'expires_at')
    list_filter = ('is_active', 'created_at', 'expires_at')
    search_fields = ('user__username', 'ip_address')
    readonly_fields = ('session_key', 'user', 'created_at', 'last_activity', 'expires_at')
    
    def session_status(self, obj):
        if obj.is_expired():
            status = 'EXPIRED'
            color = 'red'
        elif not obj.is_active:
            status = 'INACTIVE'
            color = 'orange'
        else:
            status = 'ACTIVE'
            color = 'green'
        
        return format_html(
            '<span style="background-color: {}; color: white; padding: 5px 10px; border-radius: 3px;">{}</span>',
            color,
            status
        )
    session_status.short_description = 'Status'
