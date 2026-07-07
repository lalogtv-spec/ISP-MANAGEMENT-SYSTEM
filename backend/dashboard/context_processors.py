from dashboard.admin_views import get_admin_notification_count


def admin_notification_count(request):
    """Provide the admin sidebar notification badge count for all dashboard templates."""
    if request.user.is_authenticated and request.user.is_staff:
        return {'notification_count': get_admin_notification_count()}
    return {}
