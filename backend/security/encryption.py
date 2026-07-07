"""
Encryption Service - Encrypt and decrypt sensitive data
"""
from cryptography.fernet import Fernet
from django.conf import settings
import os
import hashlib
import base64
import logging

logger = logging.getLogger(__name__)


class EncryptionService:
    """Service for encrypting and decrypting sensitive data"""
    
    @staticmethod
    def _get_cipher():
        """Get Fernet cipher for encryption/decryption"""
        try:
            # Get encryption key from settings or generate one
            encryption_key = getattr(settings, 'ENCRYPTION_KEY', None)
            
            if not encryption_key:
                # Derive a stable development key from SECRET_KEY so encrypted data remains readable.
                secret_source = getattr(settings, 'SECRET_KEY', 'dev-secret-key').encode()
                encryption_key = base64.urlsafe_b64encode(hashlib.sha256(secret_source).digest())
                logger.warning('No ENCRYPTION_KEY in settings. Using a stable SECRET_KEY-derived fallback for development.')
            
            if isinstance(encryption_key, str):
                encryption_key = encryption_key.encode()
            
            return Fernet(encryption_key)
            
        except Exception as e:
            logger.error(f'Error creating cipher: {str(e)}')
            raise
    
    @staticmethod
    def encrypt_data(data):
        """
        Encrypt sensitive data
        
        Args:
            data (str or bytes): Data to encrypt
            
        Returns:
            str: Encrypted data (base64 encoded)
        """
        try:
            if isinstance(data, str):
                data = data.encode()
            
            cipher = EncryptionService._get_cipher()
            encrypted = cipher.encrypt(data)
            
            return encrypted.decode()
            
        except Exception as e:
            logger.error(f'Encryption error: {str(e)}')
            raise
    
    @staticmethod
    def decrypt_data(encrypted_data):
        """
        Decrypt sensitive data
        
        Args:
            encrypted_data (str or bytes): Encrypted data
            
        Returns:
            str: Decrypted data
        """
        try:
            if isinstance(encrypted_data, str):
                encrypted_data = encrypted_data.encode()
            
            cipher = EncryptionService._get_cipher()
            decrypted = cipher.decrypt(encrypted_data)
            
            return decrypted.decode()
            
        except Exception as e:
            logger.error(f'Decryption error: {str(e)}')
            raise
    
    @staticmethod
    def hash_password(password):
        """
        Hash password using PBKDF2 (Django's default)
        Use Django's make_password for new passwords
        
        Args:
            password (str): Password to hash
            
        Returns:
            str: Hashed password
        """
        from django.contrib.auth.hashers import make_password
        return make_password(password)
    
    @staticmethod
    def verify_password(password, hashed_password):
        """
        Verify password against hash
        
        Args:
            password (str): Password to verify
            hashed_password (str): Hashed password
            
        Returns:
            bool: True if password matches
        """
        from django.contrib.auth.hashers import check_password
        return check_password(password, hashed_password)
    
    @staticmethod
    def hash_sensitive_data(data):
        """
        Create one-way hash of sensitive data (for comparison purposes)
        
        Args:
            data (str): Data to hash
            
        Returns:
            str: SHA256 hash
        """
        if isinstance(data, str):
            data = data.encode()
        
        return hashlib.sha256(data).hexdigest()
    
    @staticmethod
    def generate_secure_token(length=32):
        """
        Generate cryptographically secure random token
        
        Args:
            length (int): Length of token
            
        Returns:
            str: Random token (hex encoded)
        """
        return os.urandom(length // 2).hex()
    
    @staticmethod
    def mask_sensitive_data(data, show_chars=4):
        """
        Mask sensitive data for display (e.g., email, phone)
        
        Args:
            data (str): Data to mask
            show_chars (int): Number of characters to show at end
            
        Returns:
            str: Masked data
        """
        if len(data) <= show_chars:
            return '*' * len(data)
        
        mask_length = len(data) - show_chars
        return '*' * mask_length + data[-show_chars:]
    
    @staticmethod
    def encrypt_email(email):
        """Encrypt email address"""
        return EncryptionService.encrypt_data(email)
    
    @staticmethod
    def decrypt_email(encrypted_email):
        """Decrypt email address"""
        return EncryptionService.decrypt_data(encrypted_email)
    
    @staticmethod
    def encrypt_phone(phone):
        """Encrypt phone number"""
        return EncryptionService.encrypt_data(phone)
    
    @staticmethod
    def decrypt_phone(encrypted_phone):
        """Decrypt phone number"""
        return EncryptionService.decrypt_data(encrypted_phone)
    
    @staticmethod
    def encrypt_id(id_number):
        """Encrypt ID number"""
        return EncryptionService.encrypt_data(id_number)
    
    @staticmethod
    def decrypt_id(encrypted_id):
        """Decrypt ID number"""
        return EncryptionService.decrypt_data(encrypted_id)
    
    @staticmethod
    def get_encryption_key_b64():
        """
        Get base64 encoded encryption key for backup/storage
        
        Returns:
            str: Base64 encoded key
        """
        try:
            encryption_key = getattr(settings, 'ENCRYPTION_KEY', None)
            if isinstance(encryption_key, str):
                encryption_key = encryption_key.encode()
            
            import base64
            return base64.b64encode(encryption_key).decode()
            
        except Exception as e:
            logger.error(f'Error getting encryption key: {str(e)}')
            raise
