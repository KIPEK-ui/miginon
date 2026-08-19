import json

from django.conf import settings
from pywebpush import WebPushException, webpush

from .models import PushSubscription


def send_push_to_user(user, title, body, url='/'):
    """Send a device push to every browser/device `user` has enabled
    notifications on. Silently drops subscriptions the push service reports
    as gone (expired or revoked by the browser) instead of raising - a
    user's phone being off or the subscription being stale is routine, not
    an error worth surfacing to whoever triggered the notification."""
    if not (settings.VAPID_PRIVATE_KEY and settings.VAPID_PUBLIC_KEY):
        return

    payload = json.dumps({'title': title, 'body': body, 'url': url})
    for sub in PushSubscription.objects.filter(user=user):
        subscription_info = {
            'endpoint': sub.endpoint,
            'keys': {'p256dh': sub.p256dh, 'auth': sub.auth},
        }
        try:
            webpush(
                subscription_info=subscription_info,
                data=payload,
                vapid_private_key=settings.VAPID_PRIVATE_KEY,
                vapid_claims={'sub': f'mailto:{settings.VAPID_ADMIN_EMAIL}'},
            )
        except WebPushException as exc:
            status = exc.response.status_code if exc.response is not None else None
            if status in (404, 410):
                sub.delete()
