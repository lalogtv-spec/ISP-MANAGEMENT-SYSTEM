from django.db import models
from django.contrib.auth import get_user_model


User = get_user_model()


class FaceProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='face_profile')
    enabled = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Face Profile'
        verbose_name_plural = 'Face Profiles'

    def __str__(self):
        return f'FaceProfile({self.user.username})'


class FaceEnrollmentImage(models.Model):
    profile = models.ForeignKey(FaceProfile, on_delete=models.CASCADE, related_name='enrollment_images')
    image = models.ImageField(upload_to='face_db/%Y/%m/%d/')
    captured_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Face Enrollment Image'
        verbose_name_plural = 'Face Enrollment Images'

    def __str__(self):
        return f'FaceEnrollmentImage({self.profile.user.username}, {self.captured_at:%Y-%m-%d %H:%M:%S})'
