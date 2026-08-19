from django.conf import settings
from django.db.models import Q

from .models import FarmMembership


def active_farm(request):
    """Expose the signed-in user's farm memberships and the currently
    selected farm (for the farm switcher in the nav) to every template."""
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return {}

    memberships = list(
        FarmMembership.objects.filter(user=user, status=FarmMembership.Status.ACTIVE)
        .select_related('farm')
    )
    if not memberships:
        return {'my_memberships': [], 'active_membership': None, 'active_farm_obj': None}

    active_farm_id = request.session.get('active_farm_id')
    active_membership = next(
        (m for m in memberships if m.farm_id == active_farm_id), memberships[0]
    )
    request.session.setdefault('active_farm_id', active_membership.farm_id)

    from notifications.models import Notification

    notif_qs = Notification.objects.filter(farm=active_membership.farm)
    if not active_membership.can_view_all_notifications:
        notif_qs = notif_qs.filter(Q(actor=user) | Q(recipient=user))
    since = active_membership.last_notifications_read_at or active_membership.created_at
    unread_notifications_count = notif_qs.filter(created_at__gt=since).count()

    return {
        'my_memberships': memberships,
        'active_membership': active_membership,
        'active_farm_obj': active_membership.farm,
        'unread_notifications_count': unread_notifications_count,
        'vapid_public_key': getattr(settings, 'VAPID_PUBLIC_KEY', ''),
    }
