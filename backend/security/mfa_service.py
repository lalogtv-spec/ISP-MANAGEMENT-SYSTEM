"""
Multi-Factor Authentication Service - Manage MFA combinations and workflows
"""
import json
import secrets
from django.contrib.auth.models import User
from django.utils import timezone
from .models import MFASettings, LoginAttempt, AuditLog, BiometricData
from .otp_service import OTPService
from .facial_recognition import FacialRecognitionService
from .fingerprint_auth import FingerprintAuthService
import logging

logger = logging.getLogger(__name__)


class MFAService:
    """Service for managing Multi-Factor Authentication"""
    
    SUPPORTED_METHODS = [
        'password_otp',
        'password_facial',
        'password_fingerprint',
        'password_otp_facial',
        'password_otp_fingerprint',
        'password_otp_facial_fingerprint',
    ]
    
    @staticmethod
    def enable_mfa(user, method='password_otp'):
        """
        Enable MFA for user
        
        Args:
            user (User): Django User object
            method (str): MFA method to use
            
        Returns:
            dict: {
                'success': bool,
                'message': str,
                'backup_codes': list,
                'error': str or None
            }
        """
        try:
            if method not in MFAService.SUPPORTED_METHODS:
                return {
                    'success': False,
                    'message': None,
                    'backup_codes': [],
                    'error': f'Invalid MFA method: {method}'
                }
            
            # Generate backup codes
            backup_codes = MFAService._generate_backup_codes(10)
            
            # Create or update MFA settings
            mfa_settings, created = MFASettings.objects.get_or_create(
                user=user,
                defaults={
                    'is_enabled': True,
                    'method': method,
                    'backup_codes': json.dumps(backup_codes),
                    'enabled_at': timezone.now()
                }
            )
            
            if not created:
                mfa_settings.is_enabled = True
                mfa_settings.method = method
                mfa_settings.backup_codes = json.dumps(backup_codes)
                mfa_settings.enabled_at = timezone.now()
                mfa_settings.save()
            
            # Update user security profile
            user.security_profile.mfa_enabled = True
            user.security_profile.mfa_method = method
            user.security_profile.save()
            
            # Log audit event
            AuditLog.objects.create(
                user=user,
                action_type='mfa_enable',
                description=f'MFA enabled with method: {method}',
                status='success'
            )
            
            logger.info(f'MFA enabled for user {user.username} with method {method}')
            
            return {
                'success': True,
                'message': f'MFA enabled with {method} method',
                'backup_codes': backup_codes,
                'error': None
            }
            
        except Exception as e:
            logger.error(f'Error enabling MFA for {user.username}: {str(e)}')
            return {
                'success': False,
                'message': None,
                'backup_codes': [],
                'error': f'Error enabling MFA: {str(e)}'
            }
    
    @staticmethod
    def disable_mfa(user):
        """
        Disable MFA for user
        
        Args:
            user (User): Django User object
            
        Returns:
            dict: {'success': bool, 'message': str}
        """
        try:
            mfa_settings = MFASettings.objects.filter(user=user)
            mfa_settings.update(is_enabled=False)
            
            user.security_profile.mfa_enabled = False
            user.security_profile.save()
            
            AuditLog.objects.create(
                user=user,
                action_type='mfa_disable',
                description='MFA disabled',
                status='success'
            )
            
            return {
                'success': True,
                'message': 'MFA disabled successfully'
            }
            
        except Exception as e:
            logger.error(f'Error disabling MFA for {user.username}: {str(e)}')
            return {
                'success': False,
                'message': f'Error disabling MFA: {str(e)}'
            }
    
    @staticmethod
    def get_mfa_settings(user):
        """Get MFA settings for user"""
        try:
            return MFASettings.objects.get(user=user)
        except MFASettings.DoesNotExist:
            return None
    
    @staticmethod
    def is_mfa_enabled(user):
        """Check if MFA is enabled for user"""
        mfa = MFAService.get_mfa_settings(user)
        return mfa and mfa.is_enabled
    
    @staticmethod
    def get_required_factors(user):
        """
        Get list of authentication factors required for MFA
        
        Args:
            user (User): Django User object
            
        Returns:
            list: Required authentication factors
        """
        try:
            mfa_settings = MFAService.get_mfa_settings(user)
            
            if not mfa_settings or not mfa_settings.is_enabled:
                return []
            
            method = mfa_settings.method
            factors = []
            
            if 'password' in method:
                factors.append('password')
            if 'otp' in method:
                factors.append('otp')
            if 'facial' in method:
                factors.append('facial')
            if 'fingerprint' in method:
                factors.append('fingerprint')
            
            return factors
            
        except Exception as e:
            logger.error(f'Error getting required factors: {str(e)}')
            return []

    @staticmethod
    def get_login_required_factors(user):
        """
        Get the factors that should be enforced during sign-in.

        The login page now handles face and fingerprint sign-in directly.
        This helper focuses on OTP-based sign-in rules for password and
        existing server-side flows.
        """
        try:
            mfa_settings = MFAService.get_mfa_settings(user)
            if not mfa_settings or not mfa_settings.is_enabled:
                return []

            factors = []
            if (
                mfa_settings.allow_otp_login
                or mfa_settings.require_on_every_login
                or mfa_settings.require_on_suspicious_login
            ):
                factors.append('otp')
            return factors
        except Exception as e:
            logger.error(f'Error getting login factors: {str(e)}')
            return MFAService.get_required_factors(user)
    
    @staticmethod
    def initiate_mfa_verification(user, ip_address='', device_info='', reason='login'):
        """
        Start MFA verification process
        
        Args:
            user (User): Django User object
            ip_address (str): IP address
            device_info (str): Device information
            reason (str): Reason for verification
            
        Returns:
            dict: {
                'success': bool,
                'required_factors': list,
                'message': str
            }
        """
        try:
            required_factors = MFAService.get_login_required_factors(user)
            
            if not required_factors:
                return {
                    'success': False,
                    'required_factors': [],
                    'message': 'No MFA or biometric login factors are configured for this account.'
                }
            
            # Send OTP if required
            if 'otp' in required_factors:
                otp_result = OTPService.send_otp(
                    user,
                    ip_address=ip_address,
                    user_agent=device_info
                )
                
                if not otp_result['success']:
                    return {
                        'success': False,
                        'required_factors': required_factors,
                        'message': f'Failed to send OTP: {otp_result["error"]}'
                    }
            
            # Log audit event
            AuditLog.objects.create(
                user=user,
                action_type='security_event',
                description=f'MFA verification initiated - Factors: {", ".join(required_factors)}',
                ip_address=ip_address,
                device_info=device_info,
                status='success'
            )
            
            return {
                'success': True,
                'required_factors': required_factors,
                'message': f'MFA verification required - Factors: {", ".join(required_factors)}'
            }
            
        except Exception as e:
            logger.error(f'Error initiating MFA verification: {str(e)}')
            return {
                'success': False,
                'required_factors': [],
                'message': f'Error initiating MFA: {str(e)}'
            }
    
    @staticmethod
    def verify_mfa_factors(user, factors_data, ip_address='', device_info=''):
        """
        Verify all required MFA factors
        
        Args:
            user (User): Django User object
            factors_data (dict): {
                'otp': 'code',
                'facial': image_bytes,
                'fingerprint': template_data
            }
            ip_address (str): IP address
            device_info (str): Device information
            
        Returns:
            dict: {
                'success': bool,
                'verified_factors': list,
                'failed_factors': list,
                'message': str
            }
        """
        try:
            required_factors = MFAService.get_login_required_factors(user)
            verified_factors = []
            failed_factors = []
            
            # Verify each required factor
            for factor in required_factors:
                if factor == 'otp':
                    otp_code = factors_data.get('otp', '')
                    result = OTPService.verify_otp(user, otp_code, ip_address, device_info)
                    
                    if result['success']:
                        verified_factors.append('otp')
                    else:
                        failed_factors.append(('otp', result['error']))
                
                elif factor == 'facial':
                    facial_image = factors_data.get('facial')
                    if facial_image:
                        result = FacialRecognitionService.verify_face(
                            user,
                            facial_image,
                            ip_address=ip_address,
                            device_info=device_info,
                            reason='mfa_verification'
                        )
                        
                        if result['success']:
                            verified_factors.append('facial')
                        else:
                            failed_factors.append(('facial', result['error']))
                    else:
                        failed_factors.append(('facial', 'No facial image provided'))
                
                elif factor == 'fingerprint':
                    fingerprint_data = factors_data.get('fingerprint')
                    if fingerprint_data:
                        result = FingerprintAuthService.verify_fingerprint(
                            user,
                            fingerprint_data,
                            ip_address=ip_address,
                            device_info=device_info,
                            reason='mfa_verification'
                        )
                        
                        if result['success']:
                            verified_factors.append('fingerprint')
                        else:
                            failed_factors.append(('fingerprint', result['error']))
                    else:
                        failed_factors.append(('fingerprint', 'No fingerprint data provided'))
            
            # Check if all factors verified
            all_verified = len(verified_factors) == len(required_factors)
            
            if all_verified:
                # Update last verified timestamp
                mfa_settings = MFAService.get_mfa_settings(user)
                if mfa_settings:
                    mfa_settings.last_verified_at = timezone.now()
                    mfa_settings.save()
                
                # Log audit event
                AuditLog.objects.create(
                    user=user,
                    action_type='security_event',
                    description=f'MFA verification successful - All {len(verified_factors)} factors verified',
                    ip_address=ip_address,
                    device_info=device_info,
                    status='success'
                )
            else:
                # Log failed factors
                AuditLog.objects.create(
                    user=user,
                    action_type='security_event',
                    description=f'MFA verification failed - Verified: {verified_factors}, Failed: {[f[0] for f in failed_factors]}',
                    ip_address=ip_address,
                    device_info=device_info,
                    status='failed'
                )
            
            return {
                'success': all_verified,
                'verified_factors': verified_factors,
                'failed_factors': failed_factors,
                'message': f'Verified {len(verified_factors)}/{len(required_factors)} factors'
            }
            
        except Exception as e:
            logger.error(f'Error verifying MFA factors: {str(e)}')
            return {
                'success': False,
                'verified_factors': [],
                'failed_factors': [],
                'message': f'Error verifying factors: {str(e)}'
            }
    
    @staticmethod
    def verify_backup_code(user, code):
        """
        Verify backup code for MFA recovery
        
        Args:
            user (User): Django User object
            code (str): Backup code to verify
            
        Returns:
            dict: {'success': bool, 'message': str}
        """
        try:
            mfa_settings = MFAService.get_mfa_settings(user)
            
            if not mfa_settings:
                return {
                    'success': False,
                    'message': 'MFA not configured'
                }
            
            backup_codes = mfa_settings.get_backup_codes()
            used_codes = mfa_settings.get_used_codes()
            
            if code not in backup_codes:
                return {
                    'success': False,
                    'message': 'Invalid backup code'
                }
            
            if code in used_codes:
                return {
                    'success': False,
                    'message': 'Backup code already used'
                }
            
            # Mark code as used
            mfa_settings.mark_backup_code_as_used(code)
            
            AuditLog.objects.create(
                user=user,
                action_type='security_event',
                description='MFA backup code used',
                status='success'
            )
            
            return {
                'success': True,
                'message': 'Backup code verified successfully'
            }
            
        except Exception as e:
            logger.error(f'Error verifying backup code: {str(e)}')
            return {
                'success': False,
                'message': f'Error: {str(e)}'
            }
    
    @staticmethod
    def _generate_backup_codes(count=10, code_length=8):
        """
        Generate backup codes for account recovery
        
        Args:
            count (int): Number of codes to generate
            code_length (int): Length of each code
            
        Returns:
            list: List of backup codes
        """
        codes = []
        for _ in range(count):
            code = secrets.token_hex(code_length // 2)
            codes.append(code)
        return codes
