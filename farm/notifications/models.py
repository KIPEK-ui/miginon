from django.conf import settings
from django.db import models


class Notification(models.Model):
    class Verb(models.TextChoices):
        CREATED = 'created', 'added'
        UPDATED = 'updated', 'updated'
        DELETED = 'deleted', 'removed'

    farm = models.ForeignKey('farms.Farm', on_delete=models.CASCADE, related_name='notifications')
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+'
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE,
        related_name='received_notifications',
        help_text='Set when this notification is targeted at one specific user '
                   '(e.g. a task assignment) rather than the general farm activity feed.'
    )
    verb = models.CharField(max_length=10, choices=Verb.choices)
    kind = models.CharField(max_length=40, help_text='e.g. "cow", "milk record", "worker"')
    description = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['farm', '-created_at'])]

    def __str__(self):
        who = self.actor.get_full_name() if self.actor else 'Someone'
        return f'{who} {self.get_verb_display()} {self.kind}: {self.description}'


class PushSubscription(models.Model):
    """A browser/device endpoint registered via the Push API (see
    static/pwa/serviceworker.js and partials/notification_permission_banner.html).
    One user can have several - one per browser/device they enabled
    notifications on."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='push_subscriptions'
    )
    endpoint = models.URLField(max_length=500, unique=True)
    p256dh = models.CharField(max_length=255)
    auth = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.user} - {self.endpoint[:40]}...'
