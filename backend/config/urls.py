from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from dashboard.views import login_view, mfa_challenge_view, google_login_view

urlpatterns = [
    path('', include(('dashboard.urls', 'dashboard'), namespace='dashboard')),
    path('api/', include('api.urls')),
    # Face authentication endpoints (enroll / login / enable)
    path('accounts/face-auth/', include('face_auth.urls')),
    path('admin/', admin.site.urls),
    path('accounts/login/', login_view, name='login'),
    path('accounts/google-login/', google_login_view, name='google-login'),
    path('accounts/mfa-challenge/', mfa_challenge_view, name='mfa-challenge'),
    path('accounts/logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
