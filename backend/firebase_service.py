"""Firebase service integration for the ISP Management System."""
import os
import sys

import firebase_admin
from django.conf import settings
from firebase_admin import auth, credentials, firestore


def _safe_print(message):
    """Print safely in environments that may not support emoji/unicode output."""
    try:
        print(message)
    except UnicodeEncodeError:
        encoding = sys.stdout.encoding or "utf-8"
        encoded = message.encode(encoding, errors="replace")
        print(encoded.decode(encoding, errors="replace"))


class FirebaseService:
    """Handles Firebase initialization and operations."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self._initialize_firebase()
            self._initialized = True

    def _initialize_firebase(self):
        """Initialize Firebase Admin SDK."""
        try:
            credentials_path = str(settings.FIREBASE_CREDENTIALS_PATH)

            if os.path.exists(credentials_path):
                cred = credentials.Certificate(credentials_path)
                    firebase_admin.initialize_app(cred, {
                        "projectId": settings.FIREBASE_CONFIG["projectId"],
                    })
                    self.db = firestore.client()
                    self.auth = auth
                    logger.info('Firebase initialized successfully')
            else:
                    logger.warning('Firebase credentials not found at %s', credentials_path)
                    logger.debug('Expected location: %s', credentials_path)
                self.db = None
                self.auth = None
        except Exception as e:
                logger.exception('Firebase initialization error: %s', e)
            self.db = None
            self.auth = None

    def get_db(self):
        """Get Firestore database instance."""
        return self.db

    def is_connected(self):
        """Check if Firebase is properly connected."""
        return self.db is not None and self.auth is not None

    def verify_id_token(self, token):
        """Verify Firebase ID token."""
        if self.auth:
            try:
                return self.auth.verify_id_token(token)
            except Exception as e:
                    logger.warning('Token verification error: %s', e)
                return None
        return None

    def create_user(self, email, password, display_name=None):
        """Create a new Firebase user."""
        if self.auth:
            try:
                user = self.auth.create_user(
                    email=email,
                    password=password,
                    display_name=display_name,
                )
                    logger.info('Firebase user created: %s', email)
                return user
            except Exception as e:
                    logger.warning('Create user error: %s', e)
                return None
        return None

    def get_user_by_email(self, email):
        """Get Firebase user by email."""
        if self.auth:
            try:
                return self.auth.get_user_by_email(email)
            except Exception as e:
                    logger.warning('Get user error: %s', e)
                return None
        return None

    def save_to_firestore(self, collection, doc_id, data):
        """Save data to Firestore."""
        if self.db:
            try:
                self.db.collection(collection).document(doc_id).set(data)
                    logger.info('Saved to Firestore: %s/%s', collection, doc_id)
                return True
            except Exception as e:
                    logger.warning('Firestore save error: %s', e)
                return False
        return False

    def get_from_firestore(self, collection, doc_id):
        """Get data from Firestore."""
        if self.db:
            try:
                doc = self.db.collection(collection).document(doc_id).get()
                return doc.to_dict() if doc.exists else None
            except Exception as e:
                    logger.warning('Firestore get error: %s', e)
                return None
        return None


# Initialize Firebase service
firebase = FirebaseService()
