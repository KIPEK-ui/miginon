from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class CreditScoreSnapshot(models.Model):
    """Append-only, like a finance Transaction's anchor - never overwritten,
    so a lender-facing audit trail can show score evolution over time with
    each historical value provably unaltered. category_breakdown and
    feature_values hold ONLY this farm's own numbers, never another farm's
    or the population matrix itself - see creditscore.services."""

    class Tier(models.TextChoices):
        POOR = 'poor', _('Poor')
        FAIR = 'fair', _('Fair')
        GOOD = 'good', _('Good')
        EXCELLENT = 'excellent', _('Excellent')

    class Method(models.TextChoices):
        POPULATION = 'population', _('Population PCA/KMeans')
        PROVISIONAL = 'provisional', _('Provisional composite (limited peer data)')

    farm = models.ForeignKey('farms.Farm', on_delete=models.CASCADE, related_name='credit_score_snapshots')
    computed_at = models.DateTimeField(auto_now_add=True)
    score = models.PositiveSmallIntegerField()
    tier = models.CharField(max_length=10, choices=Tier.choices)
    method = models.CharField(max_length=12, choices=Method.choices)
    population_size = models.PositiveIntegerField()
    category_breakdown = models.JSONField(default=dict, blank=True)
    feature_values = models.JSONField(default=dict, blank=True)
    contributions = models.JSONField(
        default=list, blank=True,
        help_text=_('Exact per-feature drivers of the score - see creditscore.explain.')
    )
    explanation = models.CharField(max_length=255, blank=True)
    content_hash = models.CharField(max_length=64, blank=True)
    hedera_topic_id = models.CharField(max_length=20, blank=True)
    hedera_sequence_number = models.PositiveIntegerField(null=True, blank=True)
    hedera_consensus_timestamp = models.CharField(max_length=40, blank=True)
    hedera_anchored_at = models.DateTimeField(null=True, blank=True)
    computed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+'
    )

    class Meta:
        ordering = ['-computed_at']

    def __str__(self):
        return f'{self.farm.name} - {self.score} ({self.get_tier_display()})'
