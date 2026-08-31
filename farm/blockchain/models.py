from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class HederaConfig(models.Model):
    """Singleton (always pk=1) holding the platform's shared Hedera token/
    topic IDs. These are NOT secrets - they're public identifiers anyone can
    already look up on HashScan once a token/topic exists - so they live
    here in the database rather than in .env, and are created automatically
    on first use (see blockchain.services._ensure_id) instead of requiring
    a manual setup step. Only the operator account's credentials
    (HEDERA_OPERATOR_ID/HEDERA_OPERATOR_KEY) stay in .env, since those ARE
    secrets."""

    cow_nft_token_id = models.CharField(max_length=20, blank=True)
    harvest_nft_token_id = models.CharField(max_length=20, blank=True)
    fiq_token_id = models.CharField(max_length=20, blank=True)
    prediction_topic_id = models.CharField(max_length=20, blank=True)
    finance_topic_id = models.CharField(max_length=20, blank=True)
    credit_score_topic_id = models.CharField(max_length=20, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'Hedera config'

    def __str__(self):
        return 'Hedera platform config'

    @classmethod
    def load(cls):
        obj, _created = cls.objects.get_or_create(pk=1)
        return obj


class MilkProductionCertificate(models.Model):
    farm = models.ForeignKey('farms.Farm', on_delete=models.CASCADE, related_name='milk_certificates')
    start_date = models.DateField()
    end_date = models.DateField()
    total_liters = models.DecimalField(max_digits=10, decimal_places=2)
    fiq_amount = models.DecimalField(max_digits=12, decimal_places=2, help_text='total_liters * FIQ_REWARD_PER_LITER.')
    hedera_transaction_id = models.CharField(max_length=40, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-end_date', '-created_at']

    def __str__(self):
        return f'{self.farm.name} - {self.start_date} to {self.end_date} ({self.total_liters}L)'


class FiqLedgerEntry(models.Model):
    """FIQ custody stays entirely in the admin/treasury Hedera account (see
    blockchain.services) - a farm never holds its own on-chain balance, so
    this table is the source of truth for "how much FIQ has this farm
    earned." Each row corresponds to one successful mint_fiq() call."""

    class Reason(models.TextChoices):
        COW_REGISTERED = 'cow_registered', _('Cow registered')
        HARVEST_LOGGED = 'harvest_logged', _('Harvest logged')
        MILK_CERTIFICATE = 'milk_certificate', _('Milk production certificate')
        TASK_COMPLETED = 'task_completed', _('Task completed')
        DATA_RECORDED = 'data_recorded', _('Data recorded')

    farm = models.ForeignKey('farms.Farm', on_delete=models.CASCADE, related_name='fiq_ledger_entries')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    reason = models.CharField(max_length=20, choices=Reason.choices)
    hedera_transaction_id = models.CharField(max_length=40, blank=True)
    # Exactly one of these is set, matching `reason` - a plain FK per source
    # type is simpler and more query-friendly than a GenericForeignKey for
    # only 5 known trigger types.
    cow = models.ForeignKey('cows.Cow', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    crop_activity = models.ForeignKey('crops.CropActivity', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    milk_certificate = models.ForeignKey(MilkProductionCertificate, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    task = models.ForeignKey('tasks.Task', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    # Who did the work this entry rewards - a task's assignee, or the worker
    # whose logged records were batch-rewarded (see DATA_RECORDED below).
    # Custody/ownership of the FIQ itself still stays farm-level (see the
    # class docstring) - this is attribution for the wallet's per-worker
    # breakdown, not a separate per-user balance.
    earned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='fiq_earned'
    )
    # DATA_RECORDED only - milk/feeding/crop-activity/stock-movement logging
    # is too frequent to mint per record (see blockchain.services), so a
    # manager/farmer periodically batch-rewards a worker's logged records
    # over a date range instead, same principle as MilkProductionCertificate.
    period_start = models.DateField(null=True, blank=True)
    period_end = models.DateField(null=True, blank=True)
    record_count = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'FIQ ledger entries'

    def __str__(self):
        return f'{self.farm.name} +{self.amount} FIQ ({self.get_reason_display()})'
