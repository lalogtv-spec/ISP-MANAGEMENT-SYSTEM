import os
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from .forms import EnableFaceLoginForm, FaceEnrollmentForm, FaceLoginForm
from .models import FaceProfile
from .services import FaceAuthService
from django.views.decorators.csrf import csrf_exempt
import base64
from django.contrib.auth import authenticate
from django.http import HttpResponse


@require_http_methods(['GET', 'POST'])
@login_required
def face_enroll_view(request):
    profile, _ = FaceProfile.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        form = FaceEnrollmentForm(request.POST)
        if form.is_valid():
            image_payload = form.cleaned_data['face_image_data']
            image_list = image_payload if isinstance(image_payload, list) else [image_payload]

            if not image_list:
                messages.error(request, 'No face images were captured.')
            else:
                    # Previously we required the current password to replace enrollment; confirm removed to simplify flow

                validation_errors = []
                for image_data in image_list:
                    valid, error = FaceAuthService.validate_image_content(image_data)
                    if not valid:
                        validation_errors.append(error)
                        break

                if validation_errors:
                    messages.error(request, validation_errors[0])
                else:
                    FaceAuthService.save_enrollment_images(request.user, image_list)
                    profile.enabled = True
                    profile.save(update_fields=['enabled', 'updated_at'])
                    messages.success(request, f'Face enrollment succeeded with {len(image_list)} captures. You can now use facial login.')
                    return redirect('face-auth-enroll')
    else:
        form = FaceEnrollmentForm()

    enrollment_images = profile.enrollment_images.all() if profile.pk else []
    return render(request, 'face_auth/face_enroll.html', {
        'form': form,
        'profile': profile,
        'enrollment_images': enrollment_images,
    })


@require_http_methods(['GET', 'POST'])
def face_login_view(request):
    if request.method == 'POST':
        form = FaceLoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            image_data = form.cleaned_data['face_image_data']
            temp_path = FaceAuthService.create_temp_image(image_data)
            try:
                from django.contrib.auth import get_user_model
                from django.db.models import Q

                User = get_user_model()
                user = User.objects.filter(Q(username__iexact=username) | Q(email__iexact=username)).first()

                if user is None:
                    return JsonResponse({'success': False, 'error': 'User account not found.'}, status=404)

                profile = getattr(user, 'face_profile', None)
                if profile is None or not profile.enabled:
                    return JsonResponse({'success': False, 'error': 'Face login is not enabled for this account.'}, status=400)

                result = FaceAuthService.verify_face(user.username, temp_path)
                if not result['success']:
                    return JsonResponse({'success': False, 'error': result['error']}, status=400)

                if not user.is_active:
                    return JsonResponse({'success': False, 'error': 'This account is inactive.'}, status=403)

                login(request, user)
                return JsonResponse({
                    'success': True,
                    'message': 'Face verified successfully.',
                    'redirect_url': settings.LOGIN_REDIRECT_URL,
                })
            finally:
                FaceAuthService.delete_file(temp_path)

        return JsonResponse({'success': False, 'error': 'Invalid face login data.'}, status=400)

    form = FaceLoginForm()
    return render(request, 'face_auth/face_login.html', {'form': form})


@login_required
@require_http_methods(['GET', 'POST'])
def enable_face_login_view(request):
    profile, _ = FaceProfile.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        form = EnableFaceLoginForm(request.POST)
        if form.is_valid():
            profile.enabled = form.cleaned_data['enable_face_login']
            profile.save(update_fields=['enabled', 'updated_at'])
            messages.success(request, 'Facial login preference updated.')
            return redirect('face-auth-enable')
    else:
        form = EnableFaceLoginForm(initial={'enable_face_login': profile.enabled})
    return render(request, 'face_auth/face_enable.html', {'form': form, 'profile': profile})


@login_required
@require_http_methods(['POST'])
def face_enroll_stage1(request):
    """Stage 1: receive captured image(s) and store temporarily server-side.

    Returns JSON {success: True} on success.
    """
    image_payload = request.POST.get('face_image_data') or request.body and request.POST.get('face_image_data')
    if not image_payload:
        return JsonResponse({'success': False, 'error': 'No image provided'}, status=400)

    # create a temp file using existing service
    try:
        temp_path = FaceAuthService.create_temp_image(image_payload)
        # store temp path in session for this user
        request.session['face_enroll_temp'] = temp_path
        request.session.modified = True
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@require_http_methods(['POST'])
def face_enroll_confirm(request):
    """Stage 2: confirm enrollment with current password and finalize save of temp image(s)."""
    temp_path = request.session.get('face_enroll_temp')
    if not temp_path:
        return JsonResponse({'success': False, 'error': 'No pending enrollment found.'}, status=400)

    password = request.POST.get('current_password', '')
    user = authenticate(request, username=request.user.username, password=password)
    if user is None:
        return JsonResponse({'success': False, 'error': 'Invalid password.'}, status=403)

    try:
        # read temp bytes and turn into data URL
        with open(temp_path, 'rb') as f:
            raw = f.read()
        data_url = 'data:image/jpeg;base64,' + base64.b64encode(raw).decode('ascii')
        FaceAuthService.save_enrollment_images(request.user, [data_url])
        profile, _ = FaceProfile.objects.get_or_create(user=request.user)
        profile.enabled = True
        profile.save(update_fields=['enabled', 'updated_at'])
        # cleanup
        try:
            FaceAuthService.delete_file(temp_path)
        except Exception:
            pass
        request.session.pop('face_enroll_temp', None)
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
