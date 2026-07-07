from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import UserSecurityProfile


@receiver(post_save, sender=User)
def create_security_profile(sender, instance, created, **kwargs):
    if created:
        UserSecurityProfile.objects.get_or_create(user=instance)
