import datetime

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class Task(models.Model):
    class Priority(models.TextChoices):
        LOW = 'low', _('Low')
        NORMAL = 'normal', _('Normal')
        HIGH = 'high', _('High')
        URGENT = 'urgent', _('Urgent')

    class Status(models.TextChoices):
        PENDING = 'pending', _('Pending')
        IN_PROGRESS = 'in_progress', _('In progress')
        DONE = 'done', _('Done')
        CANCELLED = 'cancelled', _('Cancelled')

    farm = models.ForeignKey('farms.Farm', on_delete=models.CASCADE, related_name='tasks')
    title = models.CharField(max_length=150)
    description = models.CharField(max_length=500, blank=True)
    assigned_to = models.ForeignKey(
        'farms.FarmMembership', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='tasks'
    )
    block = models.ForeignKey(
        'farms.Block', null=True, blank=True, on_delete=models.SET_NULL, related_name='tasks'
    )
    crop = models.ForeignKey(
        'crops.Crop', null=True, blank=True, on_delete=models.SET_NULL, related_name='tasks'
    )
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.NORMAL)
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.PENDING)
    due_date = models.DateField(null=True, blank=True)
    repeat_every_days = models.PositiveIntegerField(
        null=True, blank=True,
        help_text=_(
            'If set, completing this task automatically creates the next one '
            'this many days after the due date, e.g. 90 for a quarterly deworming.'
        )
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='created_tasks'
    )
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.title} - {self.farm.name}'

    def mark_status(self, status):
        self.status = status
        self.completed_at = timezone.now() if status == self.Status.DONE else None
        self.save(update_fields=['status', 'completed_at'])

    def create_next_occurrence(self):
        """Clone this task into a fresh pending one due `repeat_every_days`
        after the current due date - called once when a recurring task is
        marked done (see tasks.views.task_status_update). Anchors off
        today when there was no due_date to advance from, so recurrence
        still works for a task that was never given one."""
        anchor = self.due_date or timezone.now().date()
        return Task.objects.create(
            farm=self.farm, title=self.title, description=self.description,
            assigned_to=self.assigned_to, block=self.block, crop=self.crop,
            priority=self.priority, due_date=anchor + datetime.timedelta(days=self.repeat_every_days),
            repeat_every_days=self.repeat_every_days, created_by=self.created_by,
        )
