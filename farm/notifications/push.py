import json
import logging

from django.conf import settings
from pywebpush import WebPushException, webpush

from .models import PushSubscription

logger = logging.getLogger(__name__)


def send_push_to_user(user, title, body, url='/'):
    """Send a device push to every browser/device `user` has enabled
    notifications on. This is always best-effort: a bad/expired subscription,
    an unreachable push relay, or any other delivery failure must never
    break the request that triggered it (e.g. assigning a task shouldn't
    500 because someone's old phone subscription is stale) - so every
    per-subscription send is isolated and failures are swallowed after
    logging, not raised. Subscriptions the push service reports as gone
    (404/410 - expired or revoked by the browser) are cleaned up."""
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
            else:
                logger.warning('Push send failed for %s (status %s): %s', user, status, exc)
        except Exception:
            logger.exception('Unexpected error sending push to %s', user)
