from django.db import models
from django.utils.translation import gettext_lazy as _


class FarmInsight(models.Model):
    """A plain-language observation about the farm's own data - milk trend,
    low stock, overdue tasks, etc. Not a scheduled job: fully recomputed
    every time the insights page is viewed (see insights.services.
    refresh_insights), the same on-demand, upsert-into-the-DB pattern as
    analysis.MilkPrediction - there's no background worker in this
    deployment to run one on a schedule. `key` identifies which detector
    produced a row so refresh_insights can update_or_create instead of
    piling up duplicates, and delete whatever key no longer applies."""

    class Category(models.TextChoices):
        MILK = 'milk', _('Milk')
        FEED = 'feed', _('Feed')
        FINANCE = 'finance', _('Finance')
        TASKS = 'tasks', _('Tasks')
        INVENTORY = 'inventory', _('Inventory')
        CROPS = 'crops', _('Crops')
        GENERAL = 'general', _('General')

    class Severity(models.TextChoices):
        INFO = 'info', _('Info')
        WARNING = 'warning', _('Warning')
        CRITICAL = 'critical', _('Critical')

    farm = models.ForeignKey('farms.Farm', on_delete=models.CASCADE, related_name='insights')
    key = models.CharField(max_length=60, help_text=_('Stable id for the detector that produced this row.'))
    category = models.CharField(max_length=10, choices=Category.choices)
    severity = models.CharField(max_length=10, choices=Severity.choices, default=Severity.INFO)
    title = models.CharField(max_length=150)
    description = models.CharField(max_length=500)
    computed_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('farm', 'key')
        # Not '-severity' - that's a plain string field, so descending order
        # would put 'warning' before 'critical' alphabetically. Severity
        # priority is sorted in Python where it's actually displayed (see
        # insights.views.overview) instead.
        ordering = ['-computed_at']

    def __str__(self):
        return f'{self.farm.name} - {self.title}'
