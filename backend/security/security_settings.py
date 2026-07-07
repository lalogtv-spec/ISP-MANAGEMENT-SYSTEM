"""
Security Settings and Configuration
Place these settings in your Django settings.py or use environment variables
"""

# Security Configuration
SECURITY_SETTINGS = {
    # OTP Settings
    'OTP': {
        'LENGTH': 6,
        'EXPIRY_MINUTES': 15,
        'MAX_ATTEMPTS': 5,
        'RESEND_COOLDOWN_SECONDS': 60,
    },
    
    # Biometric Settings
    'BIOMETRIC': {
        'FINGERPRINT_ENROLLMENT_QUALITY_THRESHOLD': 0.75,
        'FINGERPRINT_VERIFICATION_MATCH_THRESHOLD': 0.85,
        'FINGERPRINT_MIN_MINUTIAE_POINTS': 30,
    },
    
    # Login Security Settings
    'LOGIN': {
        'MAX_FAILED_ATTEMPTS': 5,
        'LOCKOUT_DURATION_MINUTES': 30,
        'SESSION_TIMEOUT_MINUTES': 30,
        'INACTIVITY_TIMEOUT_MINUTES': 30,
        'FORCE_HTTPS': True,
        'SECURE_COOKIES': True,
    },
    
    # MFA Settings
    'MFA': {
        'ENABLED_BY_DEFAULT': False,
        'REQUIRE_ON_EVERY_LOGIN': False,
        'REQUIRE_ON_SUSPICIOUS_LOGIN': True,
        'BACKUP_CODES_COUNT': 10,
        'SUPPORTED_METHODS': [
            'password_otp',
            'password_fingerprint',
            'password_otp_fingerprint',
        ]
    },
    
    # Password Policy
    'PASSWORD': {
        'MIN_LENGTH': 12,
        'REQUIRE_UPPERCASE': True,
        'REQUIRE_LOWERCASE': True,
        'REQUIRE_DIGITS': True,
        'REQUIRE_SPECIAL_CHARS': True,
        'EXPIRY_DAYS': 90,
        'HISTORY_COUNT': 5,  # Number of previous passwords to check
    },
    
    # Encryption Settings
    'ENCRYPTION': {
        'ALGORITHM': 'Fernet',  # Fernet symmetric encryption
        'ENCRYPT_SENSITIVE_FIELDS': [
            'email',
            'phone',
            'id_number'
        ]
    },
    
    # Audit Logging Settings
    'AUDIT': {
        'LOG_ALL_ACTIONS': True,
        'RETENTION_DAYS': 90,
        'ALERT_ON_SUSPICIOUS_ACTIVITY': True,
        'SUSPICIOUS_ACTIVITY_THRESHOLD': 5,  # Failed attempts threshold
    },
    
    # CORS and Request Validation
    'CORS': {
        'ALLOWED_ORIGINS': [
            'http://localhost:3000',
            'http://127.0.0.1:3000',
            'https://yourdomain.com'
        ],
        'ALLOW_CREDENTIALS': True,
    },
    
    # Email Configuration for OTP
    'EMAIL': {
        'OTP_FROM_EMAIL': 'noreply@ispmanagement.com',
        'OTP_SUBJECT': 'Your One-Time Password (OTP)',
        'USE_TLS': True,
        'BACKEND': 'django.core.mail.backends.smtp.EmailBackend',
    },
    
    # Session Configuration
    'SESSION': {
        'ENGINE': 'django.contrib.sessions.backends.db',
        'COOKIE_AGE': 1800,  # 30 minutes in seconds
        'COOKIE_SECURE': True,
        'COOKIE_HTTPONLY': True,
        'COOKIE_SAMESITE': 'Strict',
    },
    
    # IP Whitelisting/Blacklisting
    'IP_PROTECTION': {
        'ENABLE_IP_TRACKING': True,
        'ENABLE_GEOLOCATION': False,
        'ALERT_ON_NEW_IP': True,
    },
    
    # Device Fingerprinting
    'DEVICE_FINGERPRINTING': {
        'ENABLED': True,
        'TRACK_USER_AGENT': True,
        'TRACK_DEVICE_INFO': True,
        'ALLOW_MULTIPLE_SESSIONS': False,
    }
}

# Django Settings to Add
DJANGO_SECURITY_SETTINGS = {
    # HTTPS and SSL
    'SECURE_HSTS_SECONDS': 31536000,  # 1 year
    'SECURE_HSTS_INCLUDE_SUBDOMAINS': True,
    'SECURE_HSTS_PRELOAD': True,
    'SECURE_SSL_REDIRECT': True,
    'SESSION_COOKIE_SECURE': True,
    'SESSION_COOKIE_HTTPONLY': True,
    'SESSION_COOKIE_SAMESITE': 'Strict',
    'CSRF_COOKIE_SECURE': True,
    'CSRF_COOKIE_HTTPONLY': True,
    
    # Content Security Policy
    'MIDDLEWARE': [
        'django.middleware.security.SecurityMiddleware',
        'django.contrib.sessions.middleware.SessionMiddleware',
        'django.middleware.common.CommonMiddleware',
        'django.middleware.csrf.CsrfViewMiddleware',
        'django.contrib.auth.middleware.AuthenticationMiddleware',
        'django.contrib.messages.middleware.MessageMiddleware',
        'django.middleware.clickjacking.XFrameOptionsMiddleware',
        # Add custom middleware
        'security.middleware.AuditLoggingMiddleware',
        'security.middleware.SessionValidationMiddleware',
        'security.middleware.RateLimitingMiddleware',
    ],
    
    # Authentication Backends
    'AUTHENTICATION_BACKENDS': [
        'django.contrib.auth.backends.ModelBackend',
        'security.backends.EnhancedAuthenticationBackend',
    ],
    
    # Installed Apps
    'INSTALLED_APPS_TO_ADD': [
        'security',
        'corsheaders',
    ],
    
    # Input Validation
    'VALIDATE_INPUT': True,
    'MAX_BODY_SIZE': 10485760,  # 10 MB
}

# Encryption Key - MUST be set in production
# Generate with: from cryptography.fernet import Fernet; print(Fernet.generate_key())
# ENCRYPTION_KEY = b'your-encryption-key-here'

# Logging Configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[{levelname}] {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '[{levelname}] {asctime} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'logs/security.log',
            'maxBytes': 1024 * 1024 * 10,  # 10 MB
            'backupCount': 10,
            'formatter': 'verbose',
        },
        'audit_file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'logs/audit.log',
            'maxBytes': 1024 * 1024 * 50,  # 50 MB
            'backupCount': 20,
            'formatter': 'verbose',
        },
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'loggers': {
        'security': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': False,
        },
        'audit': {
            'handlers': ['audit_file'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

# Export settings
__all__ = [
    'SECURITY_SETTINGS',
    'DJANGO_SECURITY_SETTINGS',
    'LOGGING',
]
