from .models import Notification


def notify(farm, actor, verb, kind, description):
    """Record a farm activity event. Call this right after a create/update/
    delete succeeds in any module, e.g.:
        notify(request.farm, request.user, Notification.Verb.CREATED, 'cow', str(cow))
    """
    Notification.objects.create(
        farm=farm, actor=actor, verb=verb, kind=kind, description=description[:255]
    )
