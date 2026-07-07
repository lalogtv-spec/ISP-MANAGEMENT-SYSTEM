"""
Authentication Service - Handle login, account protection, and session management
"""
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.core.cache import cache
from django.utils import timezone
from datetime import timedelta
from .models import (
    UserSecurityProfile, LoginAttempt, SecuritySettings, SessionManagement,
    AuditLog
)
from .otp_service import OTPService
from .mfa_service import MFAService
import logging

logger = logging.getLogger(__name__)


class AuthenticationService:
    """Service for managing user authentication and account security"""
    LOGIN_RATE_LIMIT_WINDOW = 300
    LOGIN_RATE_LIMIT_MAX_ATTEMPTS = 10

    @staticmethod
    def _login_rate_limit_key(username, ip_address):
        return f'login-rate:{username.lower()}:{ip_address or "unknown"}'

    @staticmethod
    def _is_login_rate_limited(username, ip_address):
        key = AuthenticationService._login_rate_limit_key(username, ip_address)
        return int(cache.get(key, 0) or 0) >= AuthenticationService.LOGIN_RATE_LIMIT_MAX_ATTEMPTS

    @staticmethod
    def _increment_login_rate_limit(username, ip_address):
        key = AuthenticationService._login_rate_limit_key(username, ip_address)
        current = int(cache.get(key, 0) or 0) + 1
        cache.set(key, current, timeout=AuthenticationService.LOGIN_RATE_LIMIT_WINDOW)
        return current

    @staticmethod
    def _clear_login_rate_limit(username, ip_address):
        cache.delete(AuthenticationService._login_rate_limit_key(username, ip_address))
    
    @staticmethod
    def authenticate_user(username, password, ip_address='', user_agent='', device_info=''):
        """
        Authenticate user with password and check account status
        
        Args:
            username (str): Username or email address
            password (str): Password
            ip_address (str): IP address
            user_agent (str): User agent string
            device_info (str): Device information
            
        Returns:
            dict: {
                'success': bool,
                'user': User or None,
                'message': str,
                'requires_mfa': bool,
                'error': str or None
            }
        """
        try:
            if AuthenticationService._is_login_rate_limited(username, ip_address):
                return {
                    'success': False,
                    'user': None,
                    'message': None,
                    'requires_mfa': False,
                    'error': 'Too many login attempts. Please wait a few minutes and try again.'
                }

            # Resolve either a username or an email address so the password +
            # OTP flow matches the new login UI contract.
            user = User.objects.filter(username__iexact=username).first()
            if user is None:
                user = User.objects.filter(email__iexact=username).first()

            if user is None:
                AuthenticationService._increment_login_rate_limit(username, ip_address)
                # Log failed login attempt
                LoginAttempt.objects.create(
                    username=username,
                    status='failed',
                    ip_address=ip_address,
                    user_agent=user_agent[:500],
                    device_info=device_info,
                    reason='User not found',
                    login_method='password'
                )
                
                return {
                    'success': False,
                    'user': None,
                    'message': None,
                    'requires_mfa': False,
                    'error': 'Invalid username or password'
                }
            
            # Get security profile (create if not exists)
            security_profile, _ = UserSecurityProfile.objects.get_or_create(user=user)
            
            # Check if account is locked
            if security_profile.is_account_locked():
                LoginAttempt.objects.create(
                    user=user,
                    username=username,
                    status='locked',
                    ip_address=ip_address,
                    user_agent=user_agent[:500],
                    device_info=device_info,
                    reason=f'Account locked until {security_profile.locked_until}',
                    login_method='password'
                )
                
                return {
                    'success': False,
                    'user': None,
                    'message': None,
                    'requires_mfa': False,
                    'error': f'Account locked. Try again after {security_profile.locked_until}'
                }
            
            # Check if password is expired
            if security_profile.is_password_expired():
                return {
                    'success': False,
                    'user': None,
                    'message': None,
                    'requires_mfa': False,
                    'error': 'Password has expired. Please reset your password.'
                }
            
            # Authenticate with Django
            authenticated_user = authenticate(username=user.username, password=password)
            
            if authenticated_user is None:
                AuthenticationService._increment_login_rate_limit(username, ip_address)
                # Failed login attempt
                security_profile.failed_login_attempts += 1
                
                # Get security settings
                try:
                    security_settings = SecuritySettings.objects.first()
                    max_attempts = security_settings.max_login_attempts if security_settings else 5
                except:
                    max_attempts = 5
                
                # Lock account if too many failed attempts
                if security_profile.failed_login_attempts >= max_attempts:
                    try:
                        security_settings = SecuritySettings.objects.first()
                        lockout_minutes = security_settings.lockout_duration_minutes if security_settings else 30
                    except:
                        lockout_minutes = 30
                    
                    security_profile.account_locked = True
                    security_profile.locked_until = timezone.now() + timedelta(minutes=lockout_minutes)
                    security_profile.save()
                    
                    AuditLog.objects.create(
                        user=user,
                        action_type='account_lockout',
                        description=f'Account locked after {security_profile.failed_login_attempts} failed attempts',
                        ip_address=ip_address,
                        user_agent=user_agent[:500],
                        device_info=device_info,
                        status='warning'
                    )
                    
                    LoginAttempt.objects.create(
                        user=user,
                        username=username,
                        status='locked',
                        ip_address=ip_address,
                        user_agent=user_agent[:500],
                        device_info=device_info,
                        reason='Too many failed login attempts',
                        login_method='password'
                    )
                    
                    return {
                        'success': False,
                        'user': None,
                        'message': None,
                        'requires_mfa': False,
                        'error': f'Account locked due to too many failed attempts. Try again after {lockout_minutes} minutes.'
                    }
                
                security_profile.save()
                
                LoginAttempt.objects.create(
                    user=user,
                    username=username,
                    status='failed',
                    ip_address=ip_address,
                    user_agent=user_agent[:500],
                    device_info=device_info,
                    reason=f'Failed login attempts: {security_profile.failed_login_attempts}',
                    login_method='password'
                )
                
                return {
                    'success': False,
                    'user': None,
                    'message': None,
                    'requires_mfa': False,
                    'error': 'Invalid username or password'
                }
            
            # Successful password authentication
            AuthenticationService._clear_login_rate_limit(username, ip_address)
            security_profile.failed_login_attempts = 0
            security_profile.last_login_ip = ip_address
            security_profile.last_login_timestamp = timezone.now()
            security_profile.last_activity = timezone.now()
            security_profile.save()

            required_factors = MFAService.get_login_required_factors(user)
            otp_required = 'otp' in required_factors

            if not otp_required:
                LoginAttempt.objects.create(
                    user=user,
                    username=username,
                    status='success',
                    ip_address=ip_address,
                    user_agent=user_agent[:500],
                    device_info=device_info,
                    login_method='password',
                    completed_at=timezone.now(),
                    reason='Password accepted; no OTP required'
                )
                return {
                    'success': True,
                    'user': authenticated_user,
                    'message': 'Password authenticated successfully.',
                    'requires_mfa': False,
                    'required_factors': [],
                    'error': None
                }

            otp_result = OTPService.send_otp(
                user,
                ip_address=ip_address,
                user_agent=user_agent,
                expiry_minutes=OTPService.DEFAULT_EXPIRY_MINUTES
            )
            if not otp_result['success']:
                return {
                    'success': False,
                    'user': None,
                    'message': None,
                    'requires_mfa': False,
                    'required_factors': ['otp'],
                    'error': otp_result['error']
                }

            LoginAttempt.objects.create(
                user=user,
                username=username,
                status='otp_required',
                ip_address=ip_address,
                user_agent=user_agent[:500],
                device_info=device_info,
                login_method='password_otp',
                completed_at=timezone.now(),
                reason='Password accepted; OTP required'
            )

            return {
                'success': True,
                'user': authenticated_user,
                'message': 'Password authenticated successfully. OTP sent to email.',
                'requires_mfa': True,
                'required_factors': ['otp'],
                'error': None
            }
            
        except Exception as e:
            logger.error(f'Authentication error for user {username}: {str(e)}')
            return {
                'success': False,
                'user': None,
                'message': None,
                'requires_mfa': False,
                'error': f'Authentication error: {str(e)}'
            }
    
    @staticmethod
    def complete_login(user, ip_address='', user_agent='', device_info='', session_timeout_minutes=30, login_method=''):
        """
        Complete login process after all authentication factors verified
        
        Args:
            user (User): Authenticated user
            ip_address (str): IP address
            user_agent (str): User agent string
            device_info (str): Device information
            session_timeout_minutes (int): Session timeout duration
            
        Returns:
            dict: {
                'success': bool,
                'session_key': str,
                'message': str
            }
        """
        try:
            # Create session record
            from django.contrib.sessions.models import Session
            import uuid
            
            session_key = str(uuid.uuid4())
            expires_at = timezone.now() + timedelta(minutes=session_timeout_minutes)
            security_profile, _ = UserSecurityProfile.objects.get_or_create(user=user)
            
            session = SessionManagement.objects.create(
                user=user,
                session_key=session_key,
                ip_address=ip_address,
                user_agent=user_agent[:500],
                device_info=device_info,
                expires_at=expires_at,
                is_active=True
            )
            
            # Update security profile
            security_profile.active_session_id = session_key
            security_profile.last_activity = timezone.now()
            security_profile.save()
            
            # Log successful login
            AuditLog.objects.create(
                user=user,
                action_type='login',
                description='User login successful',
                ip_address=ip_address,
                user_agent=user_agent[:500],
                device_info=device_info,
                session_id=session_key,
                status='success'
            )
            
            LoginAttempt.objects.create(
                user=user,
                username=user.username,
                status='success',
                ip_address=ip_address,
                user_agent=user_agent[:500],
                device_info=device_info,
                login_method=login_method,
                completed_at=timezone.now()
            )
            
            logger.info(f'User {user.username} logged in successfully')
            
            return {
                'success': True,
                'session_key': session_key,
                'message': 'Login successful'
            }
            
        except Exception as e:
            logger.error(f'Error completing login for {user.username}: {str(e)}')
            return {
                'success': False,
                'session_key': None,
                'message': f'Error: {str(e)}'
            }
    
    @staticmethod
    def logout_user(user, session_key=None):
        """
        Logout user and invalidate session
        
        Args:
            user (User): User to logout
            session_key (str): Session key to invalidate
            
        Returns:
            dict: {'success': bool, 'message': str}
        """
        try:
            # Invalidate session
            if session_key:
                SessionManagement.objects.filter(
                    session_key=session_key
                ).update(is_active=False)
            else:
                SessionManagement.objects.filter(
                    user=user,
                    is_active=True
                ).update(is_active=False)
            
            # Update security profile
            user.security_profile.active_session_id = ''
            user.security_profile.save()
            
            # Log logout
            AuditLog.objects.create(
                user=user,
                action_type='logout',
                description='User logged out',
                status='success'
            )
            
            logger.info(f'User {user.username} logged out')
            
            return {
                'success': True,
                'message': 'Logged out successfully'
            }
            
        except Exception as e:
            logger.error(f'Error logging out user {user.username}: {str(e)}')
            return {
                'success': False,
                'message': f'Error: {str(e)}'
            }
    
    @staticmethod
    def validate_session(session_key, check_inactivity=True, timeout_minutes=30):
        """
        Validate if session is still active
        
        Args:
            session_key (str): Session key to validate
            check_inactivity (bool): Check for inactivity timeout
            timeout_minutes (int): Inactivity timeout threshold
            
        Returns:
            dict: {
                'valid': bool,
                'user': User or None,
                'reason': str
            }
        """
        try:
            session = SessionManagement.objects.get(session_key=session_key)
            
            if not session.is_active:
                return {
                    'valid': False,
                    'user': None,
                    'reason': 'Session invalidated'
                }
            
            if session.is_expired():
                session.is_active = False
                session.save()
                return {
                    'valid': False,
                    'user': None,
                    'reason': 'Session expired'
                }
            
            if check_inactivity and session.is_inactive_timeout(timeout_minutes):
                session.is_active = False
                session.save()
                
                AuditLog.objects.create(
                    user=session.user,
                    action_type='security_event',
                    description=f'Session expired due to inactivity ({timeout_minutes} minutes)',
                    status='warning'
                )
                
                return {
                    'valid': False,
                    'user': None,
                    'reason': 'Session expired due to inactivity'
                }
            
            # Update last activity
            session.last_activity = timezone.now()
            session.save()
            
            # Update user security profile last activity
            session.user.security_profile.last_activity = timezone.now()
            session.user.security_profile.save()
            
            return {
                'valid': True,
                'user': session.user,
                'reason': 'Session valid'
            }
            
        except SessionManagement.DoesNotExist:
            return {
                'valid': False,
                'user': None,
                'reason': 'Session not found'
            }
        except Exception as e:
            logger.error(f'Error validating session: {str(e)}')
            return {
                'valid': False,
                'user': None,
                'reason': f'Error: {str(e)}'
            }
    
    @staticmethod
    def unlock_account(user):
        """
        Manually unlock a locked account
        
        Args:
            user (User): User to unlock
            
        Returns:
            dict: {'success': bool, 'message': str}
        """
        try:
            user.security_profile.account_locked = False
            user.security_profile.locked_until = None
            user.security_profile.failed_login_attempts = 0
            user.security_profile.save()
            
            AuditLog.objects.create(
                user=user,
                action_type='account_unlock',
                description='Account manually unlocked',
                status='success'
            )
            
            return {
                'success': True,
                'message': 'Account unlocked successfully'
            }
            
        except Exception as e:
            logger.error(f'Error unlocking account for {user.username}: {str(e)}')
            return {
                'success': False,
                'message': f'Error: {str(e)}'
            }
