from django.db import models


class MilkPrediction(models.Model):
    """A snapshot of a milk-yield prediction, persisted so the dashboard
    doesn't have to explain "why did this number change" without a record,
    and so there's a history to look back on - not a scheduled job, just
    upserted whenever the prediction dashboard is viewed (see
    analysis.views), since fitting a Ridge model on one farm's data is
    cheap enough to redo per request (see analysis.ml.train)."""

    class Scope(models.TextChoices):
        COW = 'cow', 'Cow'
        BLOCK = 'block', 'Block'
        FARM = 'farm', 'Farm'

    farm = models.ForeignKey('farms.Farm', on_delete=models.CASCADE, related_name='milk_predictions')
    scope = models.CharField(max_length=10, choices=Scope.choices)
    cow = models.ForeignKey(
        'cows.Cow', null=True, blank=True, on_delete=models.CASCADE, related_name='milk_predictions'
    )
    block = models.ForeignKey(
        'farms.Block', null=True, blank=True, on_delete=models.CASCADE, related_name='milk_predictions'
    )
    predicted_date = models.DateField()
    predicted_liters = models.DecimalField(max_digits=7, decimal_places=2)
    contributions = models.JSONField(default=list, blank=True)
    explanation = models.CharField(max_length=255, blank=True)
    trained_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('farm', 'scope', 'cow', 'block', 'predicted_date')
        ordering = ['predicted_date']

    def __str__(self):
        target = self.cow or self.block or self.farm
        return f'{target} - {self.predicted_date} - {self.predicted_liters}L'
