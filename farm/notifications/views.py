from django.shortcuts import render
from django.utils import timezone

from farms.permissions import any_member_required

from .models import Notification


@any_member_required
def notification_list(request):
    membership = request.membership
    qs = Notification.objects.filter(farm=request.farm).select_related('actor')
    if not membership.can_view_all_notifications:
        qs = qs.filter(actor=request.user)
    notifications = qs[:100]

    membership.last_notifications_read_at = timezone.now()
    membership.save(update_fields=['last_notifications_read_at'])

    return render(request, 'notifications/list.html', {'notifications': notifications})
