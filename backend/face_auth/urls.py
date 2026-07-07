from django.urls import path
from . import views

urlpatterns = [
    path('enroll/', views.face_enroll_view, name='face-auth-enroll'),
    path('enroll-stage1/', views.face_enroll_stage1, name='face-auth-enroll-stage1'),
    path('enroll-confirm/', views.face_enroll_confirm, name='face-auth-enroll-confirm'),
    path('login/', views.face_login_view, name='face-auth-login'),
    path('enable/', views.enable_face_login_view, name='face-auth-enable'),
]
