from django.conf import settings
from django.db import models
from django.utils import timezone


class Task(models.Model):
    class Priority(models.TextChoices):
        LOW = 'low', 'Low'
        NORMAL = 'normal', 'Normal'
        HIGH = 'high', 'High'
        URGENT = 'urgent', 'Urgent'

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        IN_PROGRESS = 'in_progress', 'In progress'
        DONE = 'done', 'Done'
        CANCELLED = 'cancelled', 'Cancelled'

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
