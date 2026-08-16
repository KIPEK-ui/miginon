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
