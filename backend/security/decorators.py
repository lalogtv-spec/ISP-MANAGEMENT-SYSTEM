"""
Security Decorators - Protect views with authentication and authorization
"""
from functools import wraps
from django.http import HttpResponseForbidden, JsonResponse
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from .authentication import AuthenticationService
from .access_control import AccessControlService
from .audit_logs import AuditLogger
import logging

logger = logging.getLogger('security')


def require_mfa(view_func):
    """Require Multi-Factor Authentication for view"""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        
        from .mfa_service import MFAService
        if not MFAService.is_mfa_enabled(request.user):
            # Redirect to MFA setup
            return redirect('dashboard:security-settings')
        
        return view_func(request, *args, **kwargs)
    
    return wrapper


def require_permission(permission):
    """Require specific permission for view"""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')
            
            if not AccessControlService.has_permission(request.user, permission):
                AccessControlService.audit_permission_denied(
                    request.user,
                    view_func.__name__,
                    None,
                    'view'
                )
                
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'error': 'Permission denied'
                    }, status=403)
                
                return HttpResponseForbidden('Permission denied')
            
            return view_func(request, *args, **kwargs)
        
        return wrapper
    return decorator


def require_role(role):
    """Require specific role for view"""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')
            
            if not AccessControlService.has_role(request.user, role):
                AccessControlService.audit_permission_denied(
                    request.user,
                    view_func.__name__,
                    None,
                    'view'
                )
                
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'error': f'Role {role} required'
                    }, status=403)
                
                return HttpResponseForbidden(f'Role {role} required')
            
            return view_func(request, *args, **kwargs)
        
        return wrapper
    return decorator


def require_roles(*roles):
    """Require any of the specified roles"""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')
            
            has_role = any(AccessControlService.has_role(request.user, role) for role in roles)
            
            if not has_role:
                AccessControlService.audit_permission_denied(
                    request.user,
                    view_func.__name__,
                    None,
                    'view'
                )
                
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'error': f'One of roles {roles} required'
                    }, status=403)
                
                return HttpResponseForbidden(f'One of roles {roles} required')
            
            return view_func(request, *args, **kwargs)
        
        return wrapper
    return decorator


def check_session_valid(view_func):
    """Check if session is still valid (not expired or inactive)"""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        
        # Get session key
        session_key = request.session.session_key
        
        if session_key:
            from .models import SessionManagement
            try:
                session = SessionManagement.objects.get(session_key=session_key)
                
                if session.is_expired():
                    AuthenticationService.logout_user(request.user, session_key)
                    return redirect('login')
                
                if session.is_inactive_timeout():
                    AuthenticationService.logout_user(request.user, session_key)
                    return redirect('login')
                
            except SessionManagement.DoesNotExist:
                pass
        
        return view_func(request, *args, **kwargs)
    
    return wrapper


def audit_log_action(action_type, description=''):
    """Log security action"""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            try:
                # Get request metadata
                ip_address = get_client_ip(request)
                user_agent = request.META.get('HTTP_USER_AGENT', '')[:500]
                
                # Call the view
                response = view_func(request, *args, **kwargs)
                
                # Log successful action
                if request.user.is_authenticated:
                    AuditLogger.log_action(
                        user=request.user,
                        action_type=action_type,
                        description=description or view_func.__name__,
                        ip_address=ip_address,
                        user_agent=user_agent,
                        status='success'
                    )
                
                return response
            
            except Exception as e:
                # Log failed action
                if request.user.is_authenticated:
                    AuditLogger.log_action(
                        user=request.user,
                        action_type=action_type,
                        description=description or view_func.__name__,
                        ip_address=get_client_ip(request),
                        user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
                        status='failed',
                        error_message=str(e)[:500]
                    )
                
                raise
        
        return wrapper
    return decorator


def rate_limit(limit=10, period=3600):
    """Rate limit view (requests per period in seconds)"""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')
            
            from django.core.cache import cache
            from django.utils import timezone
            
            cache_key = f'rate_limit_{view_func.__name__}_{request.user.id}'
            
            current_count = cache.get(cache_key, 0)
            
            if current_count >= limit:
                return JsonResponse({
                    'error': f'Rate limit exceeded. Try again after {period} seconds.'
                }, status=429)
            
            cache.set(cache_key, current_count + 1, period)
            
            return view_func(request, *args, **kwargs)
        
        return wrapper
    return decorator


def require_https(view_func):
    """Require HTTPS connection"""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.is_secure():
            logger.warning(f'Insecure connection attempt to {view_func.__name__}')
            return HttpResponseForbidden('HTTPS required')
        
        return view_func(request, *args, **kwargs)
    
    return wrapper


def validate_csrf_token(view_func):
    """Validate CSRF token for POST requests"""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if request.method == 'POST':
            from django.middleware.csrf import CsrfViewMiddleware
            from django.http import HttpResponse
            
            csrf_middleware = CsrfViewMiddleware(lambda r: HttpResponse())
            csrf_middleware.process_request(request)
            
            if not request.csrf_processing_done:
                return HttpResponseForbidden('CSRF token invalid')
        
        return view_func(request, *args, **kwargs)
    
    return wrapper


def get_client_ip(request):
    """Get client IP address from request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    
    return ip


# Combine decorators for common scenarios
def require_authenticated_and_secure(view_func):
    """Require authentication and HTTPS"""
    @wraps(view_func)
    @login_required
    @require_https
    @check_session_valid
    def wrapper(request, *args, **kwargs):
        return view_func(request, *args, **kwargs)
    
    return wrapper


def admin_only(view_func):
    """Admin users only"""
    return require_role('admin')(view_func)


def operator_or_admin(view_func):
    """Admin or Operator"""
    return require_roles('admin', 'operator')(view_func)
