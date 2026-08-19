from .models import Notification


def notify(farm, actor, verb, kind, description, recipient=None):
    """Record a farm activity event. Call this right after a create/update/
    delete succeeds in any module, e.g.:
        notify(request.farm, request.user, Notification.Verb.CREATED, 'cow', str(cow))

    Pass `recipient` when this notification is targeted at one specific user
    (e.g. "you were assigned a task") rather than the general farm activity
    feed - that guarantees it shows up in their notification list regardless
    of role, and also pushes it to their devices (see push.py). Leave it out
    for routine activity logging; push is intentionally scoped to targeted,
    high-signal events only, so it isn't triggered here.
    """
    notification = Notification.objects.create(
        farm=farm, actor=actor, recipient=recipient, verb=verb, kind=kind, description=description[:255]
    )
    if recipient is not None:
        from .push import send_push_to_user

        who = actor.get_short_name() if actor else 'Someone'
        send_push_to_user(
            recipient,
            title=f'{farm.name}',
            body=f'{who} {notification.get_verb_display()} {kind}: {description}',
            url='/notifications/',
        )
    return notification
