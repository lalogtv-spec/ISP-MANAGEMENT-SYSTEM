"""
OTP Service - Generate, send, and verify one-time passwords via Gmail
"""
import random
import string
import hashlib
from datetime import timedelta
from django.conf import settings
from django.utils import timezone
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.contrib.auth.models import User
from .models import OTPLog, AuditLog
import logging

logger = logging.getLogger(__name__)


class OTPService:
    """Service for OTP generation, sending, and verification"""
    
    OTP_LENGTH = 6
    MAX_ATTEMPTS = 5
    DEFAULT_EXPIRY_MINUTES = 5

    @staticmethod
    def get_account_email(user):
        """Return the email saved on the user's account, with a safe fallback."""
        account_email = (user.email or '').strip()
        if account_email:
            return account_email

        try:
            from api.models import Application
            application = Application.objects.filter(user=user).exclude(email='').order_by('-created_at').first()
            if application and application.email:
                fallback_email = application.email.strip()
                # Keep the Django user record aligned with the latest saved account email.
                user.email = fallback_email
                user.save(update_fields=['email'])
                return fallback_email
        except Exception:
            pass

        return ''
    
    @staticmethod
    def generate_otp(length=OTP_LENGTH):
        """
        Generate a random OTP of specified length
        
        Args:
            length (int): Length of OTP to generate (default: 6)
            
        Returns:
            str: Generated OTP
        """
        digits = string.digits
        return ''.join(random.choice(digits) for _ in range(length))

    @staticmethod
    def _hash_otp(user, otp_code):
        return hashlib.sha256(f'{user.id}:{otp_code}'.encode('utf-8')).hexdigest()
    
    @staticmethod
    def send_otp(user, ip_address='', user_agent='', expiry_minutes=DEFAULT_EXPIRY_MINUTES):
        """
        Generate and send OTP to user's email
        
        Args:
            user (User): Django User object
            ip_address (str): IP address of the request
            user_agent (str): User agent string
            expiry_minutes (int): Minutes until OTP expires
            
        Returns:
            dict: {
                'success': bool,
                'message': str,
                'otp_log': OTPLog or None,
                'error': str or None
            }
        """
        try:
            email_user = getattr(settings, 'EMAIL_HOST_USER', '')
            email_password = getattr(settings, 'EMAIL_HOST_PASSWORD', '')
            recipient_email = OTPService.get_account_email(user)

            if not email_user or not email_password:
                return {
                    'success': False,
                    'message': None,
                    'otp_log': None,
                    'error': 'Gmail SMTP is not configured. Set EMAIL_HOST_USER and EMAIL_HOST_PASSWORD to your Gmail address and Google App Password.'
                }
            if not recipient_email:
                return {
                    'success': False,
                    'message': None,
                    'otp_log': None,
                    'error': 'No email address is saved on this account. Please update the account email first.'
                }

            # Mark any previous active OTPs as expired
            OTPLog.objects.filter(user=user, status='active').update(status='expired')
            
            # Generate OTP
            otp_code = OTPService.generate_otp()
            otp_hash = OTPService._hash_otp(user, otp_code)
            
            # Create OTP log entry
            expiry_time = timezone.now() + timedelta(minutes=expiry_minutes)
            otp_log = OTPLog.objects.create(
                user=user,
                otp_code=otp_hash,
                email_sent_to=recipient_email,
                status='active',
                expires_at=expiry_time,
                ip_address=ip_address,
                user_agent=user_agent[:500]  # Limit user_agent length
            )
            
            # Prepare email
            email_subject = 'Your OTP for Internet Payment Tracking'
            email_context = {
                'user': user,
                'otp': otp_code,
                'expiry_minutes': expiry_minutes,
                'ip_address': ip_address,
            }
            
            # Render HTML email template
            try:
                email_html = render_to_string('emails/otp_email.html', email_context)
            except:
                # Fallback if template doesn't exist
                email_html = f"""
                <html>
                    <body>
                        <h2>Your One-Time Password (OTP)</h2>
                        <p>Hello {user.first_name or user.username},</p>
                        <p>Your OTP for login is: <strong>{otp_code}</strong></p>
                        <p>This OTP will expire in {expiry_minutes} minutes.</p>
                        <p>If you didn't request this OTP, please ignore this email.</p>
                        <p><em>Request from IP: {ip_address}</em></p>
                    </body>
                </html>
                """
            
            # Send email
            email = EmailMessage(
                subject=email_subject,
                body=email_html,
                from_email=email_user,
                to=[recipient_email]
            )
            email.content_subtype = 'html'
            email.send(fail_silently=False)
            
            # Log audit event
            AuditLog.objects.create(
                user=user,
                action_type='otp_request',
                description=f'OTP requested for email {recipient_email}',
                ip_address=ip_address,
                user_agent=user_agent[:500],
                status='success'
            )
            
            logger.info(f'OTP sent to {recipient_email} for user {user.username}')
            
            return {
                'success': True,
                'message': f'OTP sent to {recipient_email}',
                'otp_log': otp_log,
                'error': None
            }
            
        except Exception as e:
            logger.error(f'Failed to send OTP for user {user.username}: {str(e)}')
            
            # Log audit event for failure
            AuditLog.objects.create(
                user=user,
                action_type='otp_request',
                description=f'OTP request failed for email {OTPService.get_account_email(user) or user.email}',
                ip_address=ip_address,
                user_agent=user_agent[:500],
                status='failed',
                error_message=str(e)
            )
            
            return {
                'success': False,
                'message': None,
                'otp_log': None,
                'error': f'Failed to send OTP: {str(e)}'
            }
    
    @staticmethod
    def verify_otp(user, otp_code, ip_address='', user_agent=''):
        """
        Verify OTP submitted by user
        
        Args:
            user (User): Django User object
            otp_code (str): OTP code to verify
            ip_address (str): IP address of the request
            user_agent (str): User agent string
            
        Returns:
            dict: {
                'success': bool,
                'message': str,
                'otp_log': OTPLog or None,
                'error': str or None
            }
        """
        try:
            # Find active OTP for user
            otp_log = OTPLog.objects.filter(
                user=user,
                status='active'
            ).first()
            
            if not otp_log:
                error_msg = 'No active OTP found. Please request a new OTP.'
                AuditLog.objects.create(
                    user=user,
                    action_type='otp_verify',
                    description='OTP verification failed - no active OTP',
                    ip_address=ip_address,
                    user_agent=user_agent[:500],
                    status='failed'
                )
                return {
                    'success': False,
                    'message': None,
                    'otp_log': None,
                    'error': error_msg
                }
            
            # Check if OTP is valid
            if not otp_log.is_valid():
                otp_log.increment_attempts()
                error_msg = f'OTP is invalid or expired. Attempts: {otp_log.verification_attempts}/{otp_log.max_attempts}'
                AuditLog.objects.create(
                    user=user,
                    action_type='otp_verify',
                    description=f'OTP verification failed - {error_msg}',
                    ip_address=ip_address,
                    user_agent=user_agent[:500],
                    status='failed'
                )
                return {
                    'success': False,
                    'message': None,
                    'otp_log': otp_log,
                    'error': error_msg
                }
            
            # Verify OTP code
            expected_hash = OTPService._hash_otp(user, otp_code.strip())
            if otp_log.otp_code != expected_hash:
                otp_log.increment_attempts()
                remaining_attempts = otp_log.max_attempts - otp_log.verification_attempts
                error_msg = f'Invalid OTP. Remaining attempts: {remaining_attempts}'
                
                AuditLog.objects.create(
                    user=user,
                    action_type='otp_verify',
                    description=f'OTP verification failed - incorrect code',
                    ip_address=ip_address,
                    user_agent=user_agent[:500],
                    status='failed'
                )
                
                return {
                    'success': False,
                    'message': None,
                    'otp_log': otp_log,
                    'error': error_msg
                }
            
            # OTP is valid - mark as used
            otp_log.mark_as_used()
            
            # Log audit event
            AuditLog.objects.create(
                user=user,
                action_type='otp_verify',
                description='OTP verification successful',
                ip_address=ip_address,
                user_agent=user_agent[:500],
                status='success'
            )
            
            logger.info(f'OTP verified for user {user.username}')
            
            return {
                'success': True,
                'message': 'OTP verified successfully',
                'otp_log': otp_log,
                'error': None
            }
            
        except Exception as e:
            logger.error(f'OTP verification failed for user {user.username}: {str(e)}')
            
            AuditLog.objects.create(
                user=user,
                action_type='otp_verify',
                description='OTP verification error',
                ip_address=ip_address,
                user_agent=user_agent[:500],
                status='failed',
                error_message=str(e)
            )
            
            return {
                'success': False,
                'message': None,
                'otp_log': None,
                'error': f'Verification error: {str(e)}'
            }
    
    @staticmethod
    def cleanup_expired_otps(days=7):
        """
        Delete old OTP logs to keep database clean
        
        Args:
            days (int): Delete OTPs older than this many days
            
        Returns:
            int: Number of OTPs deleted
        """
        cutoff_date = timezone.now() - timedelta(days=days)
        deleted_count, _ = OTPLog.objects.filter(
            created_at__lt=cutoff_date
        ).delete()
        
        logger.info(f'Cleaned up {deleted_count} old OTP logs')
        return deleted_count
    
    @staticmethod
    def get_active_otp_for_user(user):
        """
        Get current active OTP for user
        
        Args:
            user (User): Django User object
            
        Returns:
            OTPLog or None: Active OTP if exists
        """
        return OTPLog.objects.filter(
            user=user,
            status='active'
        ).first()
    
    @staticmethod
    def has_pending_otp(user):
        """
        Check if user has a pending OTP
        
        Args:
            user (User): Django User object
            
        Returns:
            bool: True if user has active OTP
        """
        return OTPLog.objects.filter(
            user=user,
            status='active'
        ).exists()
    
    @staticmethod
    def get_otp_expiry_time(user):
        """
        Get remaining time for active OTP
        
        Args:
            user (User): Django User object
            
        Returns:
            dict: {
                'minutes': int,
                'seconds': int,
                'expired': bool
            }
        """
        otp = OTPService.get_active_otp_for_user(user)
        
        if not otp:
            return {
                'minutes': 0,
                'seconds': 0,
                'expired': True
            }
        
        time_remaining = otp.expires_at - timezone.now()
        
        if time_remaining.total_seconds() <= 0:
            return {
                'minutes': 0,
                'seconds': 0,
                'expired': True
            }
        
        minutes = int(time_remaining.total_seconds() // 60)
        seconds = int(time_remaining.total_seconds() % 60)
        
        return {
            'minutes': minutes,
            'seconds': seconds,
            'expired': False
        }
