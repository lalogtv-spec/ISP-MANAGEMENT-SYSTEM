from django.contrib import admin
from .models import FaceProfile, FaceEnrollmentImage


@admin.register(FaceProfile)
class FaceProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'enabled', 'created_at', 'updated_at')
    search_fields = ('user__username', 'user__email')
    list_filter = ('enabled',)


@admin.register(FaceEnrollmentImage)
class FaceEnrollmentImageAdmin(admin.ModelAdmin):
    list_display = ('profile', 'captured_at', 'image')
    search_fields = ('profile__user__username',)
