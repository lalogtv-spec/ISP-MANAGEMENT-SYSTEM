"""
Audit Logging Utilities - Logging and monitoring security events
"""
from django.contrib.auth.models import User
from .models import AuditLog, LoginAttempt, BiometricVerification
from datetime import timedelta
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


class AuditLogger:
    """Utility class for audit logging"""
    
    @staticmethod
    def log_action(user, action_type, description, ip_address='', user_agent='',
                   device_info='', status='success', error_message='', session_id='', related_user=None):
        """
        Log security action to audit trail
        
        Args:
            user (User): User performing action
            action_type (str): Type of action
            description (str): Action description
            ip_address (str): IP address
            user_agent (str): User agent
            device_info (str): Device information
            status (str): Action status (success, failed, warning)
            error_message (str): Error message if failed
            session_id (str): Session ID
            related_user (User): Related user (for admin actions)
            
        Returns:
            AuditLog: Created audit log entry
        """
        try:
            audit_log = AuditLog.objects.create(
                user=user,
                action_type=action_type,
                description=description,
                ip_address=ip_address,
                user_agent=user_agent[:500] if user_agent else '',
                device_info=device_info,
                status=status,
                error_message=error_message[:500] if error_message else '',
                session_id=session_id,
                related_user=related_user
            )
            
            return audit_log
            
        except Exception as e:
            logger.error(f'Error creating audit log: {str(e)}')
            return None
    
    @staticmethod
    def log_login(user, status='success', ip_address='', user_agent='', device_info=''):
        """Log login attempt"""
        return AuditLogger.log_action(
            user=user,
            action_type='login',
            description=f'User login - {status}',
            ip_address=ip_address,
            user_agent=user_agent,
            device_info=device_info,
            status='success' if status == 'success' else 'failed'
        )
    
    @staticmethod
    def log_logout(user, ip_address='', user_agent='', device_info=''):
        """Log logout"""
        return AuditLogger.log_action(
            user=user,
            action_type='logout',
            description='User logout',
            ip_address=ip_address,
            user_agent=user_agent,
            device_info=device_info,
            status='success'
        )
    
    @staticmethod
    def log_otp_request(user, email, ip_address='', user_agent=''):
        """Log OTP request"""
        return AuditLogger.log_action(
            user=user,
            action_type='otp_request',
            description=f'OTP requested for {email}',
            ip_address=ip_address,
            user_agent=user_agent,
            status='success'
        )
    
    @staticmethod
    def log_otp_verification(user, status='success', ip_address='', user_agent=''):
        """Log OTP verification attempt"""
        return AuditLogger.log_action(
            user=user,
            action_type='otp_verify',
            description=f'OTP verification - {status}',
            ip_address=ip_address,
            user_agent=user_agent,
            status='success' if status == 'success' else 'failed'
        )
    
    @staticmethod
    def log_facial_enrollment(user, ip_address='', device_info=''):
        """Log facial recognition enrollment"""
        return AuditLogger.log_action(
            user=user,
            action_type='facial_enroll',
            description='Facial recognition data enrolled',
            ip_address=ip_address,
            device_info=device_info,
            status='success'
        )
    
    @staticmethod
    def log_facial_verification(user, status='success', ip_address='', device_info=''):
        """Log facial recognition verification attempt"""
        return AuditLogger.log_action(
            user=user,
            action_type='facial_verify',
            description=f'Facial verification - {status}',
            ip_address=ip_address,
            device_info=device_info,
            status='success' if status == 'success' else 'failed'
        )
    
    @staticmethod
    def log_fingerprint_enrollment(user, ip_address='', device_info=''):
        """Log fingerprint enrollment"""
        return AuditLogger.log_action(
            user=user,
            action_type='fingerprint_enroll',
            description='Fingerprint data enrolled',
            ip_address=ip_address,
            device_info=device_info,
            status='success'
        )
    
    @staticmethod
    def log_fingerprint_verification(user, status='success', ip_address='', device_info=''):
        """Log fingerprint verification attempt"""
        return AuditLogger.log_action(
            user=user,
            action_type='fingerprint_verify',
            description=f'Fingerprint verification - {status}',
            ip_address=ip_address,
            device_info=device_info,
            status='success' if status == 'success' else 'failed'
        )
    
    @staticmethod
    def log_mfa_enable(user, method=''):
        """Log MFA enabled"""
        return AuditLogger.log_action(
            user=user,
            action_type='mfa_enable',
            description=f'MFA enabled - Method: {method}',
            status='success'
        )
    
    @staticmethod
    def log_mfa_disable(user):
        """Log MFA disabled"""
        return AuditLogger.log_action(
            user=user,
            action_type='mfa_disable',
            description='MFA disabled',
            status='success'
        )
    
    @staticmethod
    def log_password_change(user):
        """Log password change"""
        return AuditLogger.log_action(
            user=user,
            action_type='password_change',
            description='Password changed',
            status='success'
        )
    
    @staticmethod
    def log_account_lockout(user, reason='', ip_address=''):
        """Log account lockout"""
        return AuditLogger.log_action(
            user=user,
            action_type='account_lockout',
            description=f'Account locked - {reason}',
            ip_address=ip_address,
            status='warning'
        )
    
    @staticmethod
    def log_account_unlock(user):
        """Log account unlock"""
        return AuditLogger.log_action(
            user=user,
            action_type='account_unlock',
            description='Account unlocked',
            status='success'
        )
    
    @staticmethod
    def log_permission_denied(user, resource, action, ip_address=''):
        """Log permission denied event"""
        return AuditLogger.log_action(
            user=user,
            action_type='permission_change',
            description=f'Permission denied - {action} on {resource}',
            ip_address=ip_address,
            status='failed'
        )
    
    @staticmethod
    def log_admin_action(admin_user, target_user, action, description='', status='success'):
        """Log administrative action"""
        return AuditLogger.log_action(
            user=admin_user,
            action_type='admin_action',
            description=f'{action}: {description}',
            status=status,
            related_user=target_user
        )
    
    @staticmethod
    def get_user_audit_trail(user, days=30):
        """
        Get audit trail for user
        
        Args:
            user (User): User object
            days (int): Number of days to retrieve
            
        Returns:
            QuerySet: Audit logs for user
        """
        cutoff_date = timezone.now() - timedelta(days=days)
        return AuditLog.objects.filter(
            user=user,
            timestamp__gte=cutoff_date
        ).order_by('-timestamp')
    
    @staticmethod
    def get_login_history(user, limit=10):
        """
        Get login history for user
        
        Args:
            user (User): User object
            limit (int): Number of records to return
            
        Returns:
            QuerySet: Login attempts
        """
        return LoginAttempt.objects.filter(
            user=user,
            status='success'
        ).order_by('-attempted_at')[:limit]
    
    @staticmethod
    def get_failed_login_attempts(user, hours=24):
        """
        Get failed login attempts for user
        
        Args:
            user (User): User object
            hours (int): Number of hours to check
            
        Returns:
            QuerySet: Failed login attempts
        """
        cutoff_time = timezone.now() - timedelta(hours=hours)
        return LoginAttempt.objects.filter(
            user=user,
            status='failed',
            attempted_at__gte=cutoff_time
        ).order_by('-attempted_at')
    
    @staticmethod
    def get_biometric_verification_history(user, verification_type='facial', limit=10):
        """
        Get biometric verification history
        
        Args:
            user (User): User object
            verification_type (str): 'facial' or 'fingerprint'
            limit (int): Number of records to return
            
        Returns:
            QuerySet: Biometric verification attempts
        """
        return BiometricVerification.objects.filter(
            user=user,
            verification_type=verification_type
        ).order_by('-attempted_at')[:limit]
    
    @staticmethod
    def generate_security_report(user, days=30):
        """
        Generate security report for user
        
        Args:
            user (User): User object
            days (int): Number of days to include
            
        Returns:
            dict: Security report
        """
        try:
            cutoff_date = timezone.now() - timedelta(days=days)
            
            # Get statistics
            total_logins = LoginAttempt.objects.filter(
                user=user,
                status='success',
                attempted_at__gte=cutoff_date
            ).count()
            
            failed_logins = LoginAttempt.objects.filter(
                user=user,
                status='failed',
                attempted_at__gte=cutoff_date
            ).count()
            
            lockouts = AuditLog.objects.filter(
                user=user,
                action_type='account_lockout',
                timestamp__gte=cutoff_date
            ).count()
            
            otp_requests = AuditLog.objects.filter(
                user=user,
                action_type='otp_request',
                timestamp__gte=cutoff_date
            ).count()
            
            facial_attempts = BiometricVerification.objects.filter(
                user=user,
                verification_type='facial',
                attempted_at__gte=cutoff_date
            ).count()
            
            fingerprint_attempts = BiometricVerification.objects.filter(
                user=user,
                verification_type='fingerprint',
                attempted_at__gte=cutoff_date
            ).count()
            
            facial_successes = BiometricVerification.objects.filter(
                user=user,
                verification_type='facial',
                result='success',
                attempted_at__gte=cutoff_date
            ).count()
            
            fingerprint_successes = BiometricVerification.objects.filter(
                user=user,
                verification_type='fingerprint',
                result='success',
                attempted_at__gte=cutoff_date
            ).count()
            
            return {
                'user': user.username,
                'report_period_days': days,
                'generated_at': timezone.now().isoformat(),
                'login_statistics': {
                    'total_successful_logins': total_logins,
                    'total_failed_logins': failed_logins,
                    'total_lockouts': lockouts,
                    'failed_login_rate': f'{(failed_logins / (total_logins + failed_logins) * 100):.2f}%' if (total_logins + failed_logins) > 0 else '0%'
                },
                'otp_statistics': {
                    'otp_requests': otp_requests
                },
                'biometric_statistics': {
                    'facial_verification_attempts': facial_attempts,
                    'facial_verification_successes': facial_successes,
                    'facial_success_rate': f'{(facial_successes / facial_attempts * 100):.2f}%' if facial_attempts > 0 else 'N/A',
                    'fingerprint_verification_attempts': fingerprint_attempts,
                    'fingerprint_verification_successes': fingerprint_successes,
                    'fingerprint_success_rate': f'{(fingerprint_successes / fingerprint_attempts * 100):.2f}%' if fingerprint_attempts > 0 else 'N/A'
                },
                'risk_assessment': 'HIGH' if failed_logins > 5 or lockouts > 0 else 'MEDIUM' if failed_logins > 0 else 'LOW'
            }
            
        except Exception as e:
            logger.error(f'Error generating security report: {str(e)}')
            return None
