import os
from pathlib import Path

try:
    from decouple import AutoConfig
except ImportError:  # pragma: no cover - fallback if python-decouple is unavailable
    AutoConfig = None

BASE_DIR = Path(__file__).resolve().parent.parent

if AutoConfig is not None:
    env = AutoConfig(search_path=str(BASE_DIR))
else:  # pragma: no cover - fallback if python-decouple is unavailable
    def env(name, default=None, cast=str):
        value = os.environ.get(name, default)
        if value is None:
            return None
        if cast is bool:
            return str(value).lower() in ('1', 'true', 'yes', 'on')
        if cast is int:
            return int(value)
        return value


def env_list(name, default=None):
    value = env(name, default=default or '')
    if not value:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    return [item.strip() for item in str(value).split(',') if item.strip()]

import secrets

# Secret key and debug should come from the environment in production.
# If not provided (development), generate a secure random key so system
# checks that require a sufficiently long SECRET_KEY pass.
SECRET_KEY = env('SECRET_KEY', default=None)
if not SECRET_KEY:
    SECRET_KEY = os.environ.get('SECRET_KEY') or secrets.token_urlsafe(50)

# DEBUG can be toggled via environment variable. Default to True for local dev.
try:
    DEBUG = env('DEBUG', default=True, cast=bool)
except Exception:
    raw_debug = str(os.environ.get('DEBUG', '')).strip().lower()
    DEBUG = raw_debug in {'1', 'true', 'yes', 'on'}

ALLOWED_HOSTS = [
    'localhost',
    '127.0.0.1',
    'testserver',
    'internal.local',
    'example.test',
    'app.example.test',
    '[::1]',
    '.ngrok-free.app',
    '.ngrok.app',
    '.ngrok.io',
    '.lhr.life',
    '.trycloudflare.com',
]
ALLOWED_HOSTS.extend(env_list('ALLOWED_HOSTS'))
PUBLIC_HOSTNAME = env('PUBLIC_HOSTNAME', default='').strip()
CLOUDFLARED_TUNNEL_NAME = env('CLOUDFLARED_TUNNEL_NAME', default='').strip()
if PUBLIC_HOSTNAME:
    ALLOWED_HOSTS.extend([
        PUBLIC_HOSTNAME,
        f'.{PUBLIC_HOSTNAME}' if not PUBLIC_HOSTNAME.startswith('.') else PUBLIC_HOSTNAME,
    ])
ALLOWED_HOSTS = list(dict.fromkeys(ALLOWED_HOSTS))

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'corsheaders',
    'api',
    'dashboard',
    'security',  # Add security app
    'face_auth',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'config.middleware.NoCacheHtmlMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'dashboard.context_processors.admin_notification_count',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Manila'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Login Configuration
LOGIN_REDIRECT_URL = 'dashboard'
LOGIN_URL = 'login'

# CORS Configuration
CORS_ALLOWED_ORIGINS = [
    'http://localhost:5173',
    'http://localhost:3000',
    'http://127.0.0.1:5173',
]
CORS_ALLOWED_ORIGINS.extend(env_list('CORS_ALLOWED_ORIGINS'))
if PUBLIC_HOSTNAME:
    CORS_ALLOWED_ORIGINS.extend([
        f'https://{PUBLIC_HOSTNAME}',
        f'http://{PUBLIC_HOSTNAME}',
    ])
CORS_ALLOWED_ORIGINS = list(dict.fromkeys(CORS_ALLOWED_ORIGINS))

CSRF_TRUSTED_ORIGINS = [
    'https://*.ngrok-free.app',
    'https://*.ngrok.app',
    'https://*.ngrok.io',
    'https://*.lhr.life',
    'https://*.trycloudflare.com',
]
CSRF_TRUSTED_ORIGINS.extend(env_list('CSRF_TRUSTED_ORIGINS'))
if PUBLIC_HOSTNAME:
    CSRF_TRUSTED_ORIGINS.extend([
        f'https://{PUBLIC_HOSTNAME}',
        f'http://{PUBLIC_HOSTNAME}',
    ])
CSRF_TRUSTED_ORIGINS = list(dict.fromkeys(CSRF_TRUSTED_ORIGINS))

# DRF Configuration
REST_FRAMEWORK = {
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 10,
    'DEFAULT_FILTER_BACKENDS': ['django_filters.rest_framework.DjangoFilterBackend'],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
}

# Firebase Configuration
FIREBASE_CONFIG = {
    'apiKey': 'AIzaSyBnSAwEQK9kRbcLhUWJGlvPw3YjL0_1udc',
    'authDomain': 'ispmanagement-43a4c.firebaseapp.com',
    'projectId': 'ispmanagement-43a4c',
    'storageBucket': 'ispmanagement-43a4c.firebasestorage.app',
    'messagingSenderId': '702529139565',
    'appId': '1:702529139565:web:19bc7a6843cc84141a2064',
    'measurementId': 'G-M53SSGP35B'
}

# Google OAuth client ID for Google Identity Services sign-in
GOOGLE_OAUTH_CLIENT_ID = env(
    'GOOGLE_OAUTH_CLIENT_ID',
    default='702529139565-seiff5u3ll46ssl5rcrqth2o80cinl0t.apps.googleusercontent.com'
)
GOOGLE_OAUTH_CLIENT_SECRET = env('GOOGLE_OAUTH_CLIENT_SECRET', default='')
GOOGLE_OAUTH_REDIRECT_URI = env(
    'GOOGLE_OAUTH_REDIRECT_URI',
    default=''
)

# Firebase Service Account File Path
FIREBASE_CREDENTIALS_PATH = Path(env('FIREBASE_CREDENTIALS_PATH', default=str(BASE_DIR / 'serviceAccountKey.json')))

# Colab / export configuration
COLAB_EXPORT_DIR = Path(env('COLAB_EXPORT_DIR', default=str(BASE_DIR / 'colab_exports')))
FACE_SAMPLE_DIR = Path(env('FACE_SAMPLE_DIR', default=str(BASE_DIR / 'face_samples')))

# ==================== SECURITY CONFIGURATION ====================

# Notification and payment configuration
NOTIFICATIONS_USE_MOCK = env('NOTIFICATIONS_USE_MOCK', default=False, cast=bool)
NOTIFICATIONS_USE_MOCK_SMS = env('NOTIFICATIONS_USE_MOCK_SMS', default=False, cast=bool)
STRIPE_API_KEY = env('STRIPE_API_KEY', default='')
STRIPE_WEBHOOK_SECRET = env('STRIPE_WEBHOOK_SECRET', default='')

# Email Configuration for OTP
# Gmail SMTP requires a real Gmail address and a Google App Password.
EMAIL_BACKEND = env('EMAIL_BACKEND', default='django.core.mail.backends.smtp.EmailBackend')
EMAIL_HOST = env('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = env('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_TLS = env('EMAIL_USE_TLS', default=True, cast=bool)
EMAIL_HOST_USER = env('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = env('DEFAULT_FROM_EMAIL', default=EMAIL_HOST_USER)

# Twilio SMS Configuration
TWILIO_ACCOUNT_SID = env('TWILIO_ACCOUNT_SID', default='')
TWILIO_AUTH_TOKEN = env('TWILIO_AUTH_TOKEN', default='')
TWILIO_PHONE_NUMBER = env('TWILIO_PHONE_NUMBER', default='')

# Encryption Configuration
# Generate with: from cryptography.fernet import Fernet; print(Fernet.generate_key())
# Store in environment variable or settings
ENCRYPTION_KEY = os.environ.get('ENCRYPTION_KEY', None)

# Session Configuration
SESSION_ENGINE = 'django.contrib.sessions.backends.db'
SESSION_COOKIE_AGE = 1800  # 30 minutes in seconds
USE_HTTPS = env('USE_HTTPS', default=False, cast=bool)

SESSION_COOKIE_SECURE = USE_HTTPS  # Keep local HTTP login flows working by default
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_EXPIRE_AT_BROWSER_CLOSE = False

# CSRF Configuration
CSRF_COOKIE_SECURE = USE_HTTPS
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = 'Lax'  # Match SESSION_COOKIE_SAMESITE for consistency

# Security Headers
SECURE_HSTS_SECONDS = 0 if DEBUG else 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_HSTS_PRELOAD = not DEBUG
SECURE_SSL_REDIRECT = USE_HTTPS
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https') if USE_HTTPS else None
USE_X_FORWARDED_HOST = True
X_FRAME_OPTIONS = 'DENY'

# Security Settings
SECURITY_CONFIG = {
    'OTP_EXPIRY_MINUTES': 15,
    'MAX_LOGIN_ATTEMPTS': 5,
    'ACCOUNT_LOCKOUT_MINUTES': 30,
    'SESSION_TIMEOUT_MINUTES': 30,
    'ENABLE_MFA': True,
    'ENABLE_FINGERPRINT': True,
}
