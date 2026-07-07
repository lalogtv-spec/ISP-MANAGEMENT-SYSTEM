import base64
import os
import uuid
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile

try:
    import cv2
except ImportError:  # pragma: no cover - optional biometric dependency
    cv2 = None


class FaceAuthService:
    @staticmethod
    def _get_deepface():
        try:
            from deepface import DeepFace
            return DeepFace
        except ModuleNotFoundError as exc:
            raise ImportError(
                'The DeepFace library is required for face authentication. '
                'Install it with `pip install deepface` in the active environment, '
                'or disable face authentication until the dependency is available.'
            ) from exc
    TEMP_DIR = Path(settings.BASE_DIR) / 'tmp' / 'face_auth'

    @staticmethod
    def ensure_directories():
        FaceAuthService.TEMP_DIR.mkdir(parents=True, exist_ok=True)
        media_root = Path(settings.MEDIA_ROOT)
        (media_root / 'face_db').mkdir(parents=True, exist_ok=True)

    @staticmethod
    def get_user_face_dir(username):
        return Path(settings.MEDIA_ROOT) / 'face_db' / username

    @staticmethod
    def _decode_image_data(image_data):
        if isinstance(image_data, str) and 'base64,' in image_data:
            image_data = image_data.split('base64,', 1)[1]
        try:
            return base64.b64decode(image_data)
        except Exception:
            raise ValueError('Invalid base64 image data.')

    @staticmethod
    def save_enrollment_images(user, image_data_list):
        FaceAuthService.ensure_directories()
        saved_paths = []

        from .models import FaceProfile, FaceEnrollmentImage
        profile, _ = FaceProfile.objects.get_or_create(user=user)

        # Remove any existing enrollment images for this profile before saving new ones
        try:
            existing = FaceEnrollmentImage.objects.filter(profile=profile)
            for ex in existing:
                try:
                    ex.image.delete(save=False)
                except Exception:
                    pass
                try:
                    ex.delete()
                except Exception:
                    pass
        except Exception:
            pass

        for image_data in image_data_list:
            image_name = f'{uuid.uuid4().hex}.jpg'
            raw_bytes = FaceAuthService._decode_image_data(image_data)
            enrollment = FaceEnrollmentImage(profile=profile)
            enrollment.image.save(str(Path('face_db') / user.username / image_name), ContentFile(raw_bytes), save=True)
            saved_paths.append(str(Path(settings.MEDIA_ROOT) / enrollment.image.name))

        return saved_paths

    @staticmethod
    def save_enrollment_image(user, image_data):
        return FaceAuthService.save_enrollment_images(user, [image_data])[0]

    @staticmethod
    def create_temp_image(image_data):
        FaceAuthService.ensure_directories()
        raw_bytes = FaceAuthService._decode_image_data(image_data)
        temp_path = FaceAuthService.TEMP_DIR / f'{uuid.uuid4().hex}.jpg'
        with open(temp_path, 'wb') as dest:
            dest.write(raw_bytes)
        return str(temp_path)

    @staticmethod
    def delete_file(path):
        try:
            os.remove(path)
        except OSError:
            pass

    @staticmethod
    def verify_face(username, login_image_path):
        user_dir = FaceAuthService.get_user_face_dir(username)
        if not user_dir.exists() or not any(user_dir.iterdir()):
            return {
                'success': False,
                'error': 'No enrolled face images found for this user.',
                'confidence': 0.0,
            }

        image_paths = [str(path) for path in user_dir.iterdir() if path.is_file()]
        threshold = float(getattr(settings, 'FACE_AUTH_MATCH_THRESHOLD', 0.90))
        best_score = 0.0
        best_result = None

        DeepFace = FaceAuthService._get_deepface()
        for enrolled_path in image_paths:
            try:
                result = DeepFace.verify(
                    img1_path=enrolled_path,
                    img2_path=login_image_path,
                    detector_backend='opencv',
                    enforce_detection=True,
                    model_name='Facenet',
                    distance_metric='cosine',
                )
            except Exception:
                continue

            if not result or 'distance' not in result:
                continue

            confidence = 1.0 - float(result['distance'])
            if confidence > best_score:
                best_score = confidence
                best_result = result

        if best_score >= threshold:
            return {
                'success': True,
                'confidence': best_score,
                'threshold': threshold,
                'result': best_result,
            }

        return {
            'success': False,
            'error': 'Face did not match with sufficient confidence.',
            'confidence': best_score,
            'threshold': threshold,
            'result': best_result,
        }

    @staticmethod
    def validate_image_content(image_data):
        if cv2 is None:
            return False, 'OpenCV is not installed. Face authentication is unavailable.'

        FaceAuthService.ensure_directories()
        temp_path = FaceAuthService.create_temp_image(image_data)
        try:
            image = cv2.imread(temp_path)
            if image is None:
                return False, 'Uploaded file is not a valid image.'

            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
            faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5)
            if len(faces) == 0:
                return False, 'No face detected in the uploaded image.'
            if len(faces) > 1:
                return False, 'Multiple faces detected in the uploaded image.'
            return True, None
        finally:
            FaceAuthService.delete_file(temp_path)
