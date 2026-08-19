import json

from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_POST

from farms.permissions import any_member_required

from .models import Notification, PushSubscription


@any_member_required
def notification_list(request):
    membership = request.membership
    qs = Notification.objects.filter(farm=request.farm).select_related('actor')
    if not membership.can_view_all_notifications:
        qs = qs.filter(Q(actor=request.user) | Q(recipient=request.user))
    notifications = qs[:100]

    membership.last_notifications_read_at = timezone.now()
    membership.save(update_fields=['last_notifications_read_at'])

    return render(request, 'notifications/list.html', {'notifications': notifications})


@require_POST
@any_member_required
def push_subscribe(request):
    """Store (or refresh) the browser subscription the Push API handed back
    after the user granted permission - see
    partials/notification_permission_banner.html for the JS side."""
    try:
        payload = json.loads(request.body)
        endpoint = payload['endpoint']
        keys = payload['keys']
        p256dh, auth = keys['p256dh'], keys['auth']
    except (ValueError, KeyError):
        return JsonResponse({'error': 'invalid subscription payload'}, status=400)

    PushSubscription.objects.update_or_create(
        endpoint=endpoint,
        defaults={'user': request.user, 'p256dh': p256dh, 'auth': auth},
    )
    return JsonResponse({'ok': True})
