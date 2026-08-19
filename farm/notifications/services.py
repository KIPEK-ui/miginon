from .models import Notification


def notify(farm, actor, verb, kind, description, recipient=None):
    """Record a farm activity event. Call this right after a create/update/
    delete succeeds in any module, e.g.:
        notify(request.farm, request.user, Notification.Verb.CREATED, 'cow', str(cow))

    Pass `recipient` when this notification is targeted at one specific user
    (e.g. "you were assigned a task") rather than the general farm activity
    feed. For a targeted notification, `recipient.notification_delivery`
    (see accounts.settings -> Notifications) decides where it actually goes:
    in-app only, device push only, or both - so it may not create a
    Notification row, may not push, or may do both. Leave `recipient` out
    for routine activity logging, which always just logs in-app; push is
    intentionally scoped to targeted, high-signal events only.

    Returns the created Notification, or None if the recipient's preference
    means no in-app row was written for this event.
    """
    delivery = recipient.notification_delivery if recipient is not None else None

    notification = None
    if recipient is None or delivery in (recipient.NotificationDelivery.IN_APP, recipient.NotificationDelivery.BOTH):
        notification = Notification.objects.create(
            farm=farm, actor=actor, recipient=recipient, verb=verb, kind=kind, description=description[:255]
        )

    if recipient is not None and delivery in (recipient.NotificationDelivery.PUSH, recipient.NotificationDelivery.BOTH):
        from .push import send_push_to_user

        who = actor.get_short_name() if actor else 'Someone'
        verb_label = dict(Notification.Verb.choices).get(verb, verb)
        send_push_to_user(
            recipient,
            title=f'{farm.name}',
            body=f'{who} {verb_label} {kind}: {description}',
            url='/notifications/',
        )

    return notification
