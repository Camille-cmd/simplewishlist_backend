from django.contrib.auth.models import User


def admin_navbar(request):
    """Add the number of pending SSO users to the available context in templates"""
    if request.user.is_staff:
        return {
            "pending_sso_users": User.objects.filter(is_active=False).count(),
        }
    return {}
