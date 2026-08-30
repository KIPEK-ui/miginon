from datetime import time
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class Session(models.TextChoices):
    AM = 'AM', _('Morning')
    NOON = 'NOON', _('Noon')
    PM = 'PM', _('Evening')


def session_for_time(t):
    """Map a clock time to the session it falls in, so a record's AM/Noon/
    Evening label always matches when it was actually recorded rather than
    being picked independently and risking a mismatch."""
    if t < time(11, 0):
        return Session.AM
    if t < time(16, 0):
        return Session.NOON
    return Session.PM


class Cow(models.Model):
    class Status(models.TextChoices):
        ACTIVE = 'active', _('Active')
        DRY = 'dry', _('Dry')
        SOLD = 'sold', _('Sold')
        DECEASED = 'deceased', _('Deceased')

    class Category(models.TextChoices):
        CALF = 'calf', _('Calf')
        HEIFER = 'heifer', _('Heifer')
        COW = 'cow', _('Cow')
        BULL = 'bull', _('Bull')

    class Gender(models.TextChoices):
        FEMALE = 'female', _('Female')
        MALE = 'male', _('Male')

    farm = models.ForeignKey('farms.Farm', on_delete=models.CASCADE, related_name='cows')
    block = models.ForeignKey(
        'farms.Block', on_delete=models.CASCADE, related_name='cows'
    )
    tag_id = models.CharField(max_length=30, help_text=_('Ear tag / ID number'))
    name = models.CharField(max_length=60, blank=True)
    category = models.CharField(max_length=10, choices=Category.choices, default=Category.COW)
    gender = models.CharField(max_length=6, choices=Gender.choices, default=Gender.FEMALE)
    breed = models.CharField(max_length=60, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    last_calving_date = models.DateField(
        null=True, blank=True,
        help_text=_(
            'Days since calving (days in milk) is one of the strongest predictors of milk yield - '
            'used by the production analytics/prediction models.'
        )
    )
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    notes = models.CharField(max_length=255, blank=True)
    added_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='added_cows'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('farm', 'tag_id')
        ordering = ['tag_id']

    def __str__(self):
        return self.name or self.tag_id


class CowTransfer(models.Model):
    """Audit trail of a cow moving from one block/paddock to another."""

    farm = models.ForeignKey('farms.Farm', on_delete=models.CASCADE, related_name='cow_transfers')
    cow = models.ForeignKey(Cow, on_delete=models.CASCADE, related_name='transfers')
    from_block = models.ForeignKey(
        'farms.Block', on_delete=models.SET_NULL, null=True, blank=True, related_name='+'
    )
    to_block = models.ForeignKey('farms.Block', on_delete=models.CASCADE, related_name='+')
    note = models.CharField(max_length=255, blank=True)
    transferred_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='cow_transfers'
    )
    transferred_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-transferred_at']

    def __str__(self):
        return f'{self.cow.tag_id}: {self.from_block} → {self.to_block}'


class FeedingRecord(models.Model):
    farm = models.ForeignKey('farms.Farm', on_delete=models.CASCADE, related_name='feeding_records')
    block = models.ForeignKey(
        'farms.Block', on_delete=models.CASCADE, related_name='feeding_records'
    )
    date = models.DateField()
    session = models.CharField(max_length=4, choices=Session.choices)
    cows = models.ManyToManyField(Cow, related_name='feeding_records', blank=True, through='FeedingRecordCow')
    cows_count = models.PositiveIntegerField(default=0, help_text=_('Auto-filled from the cows selected below.'))
    dairy_meal_kg = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('0'))
    silage_hay_kg = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('0'))
    dairy_meal_movement = models.ForeignKey(
        'inventory.StockMovement', null=True, blank=True, editable=False,
        on_delete=models.SET_NULL, related_name='+',
        help_text=_('The Dairy Meal inventory usage this record produced.')
    )
    silage_hay_movement = models.ForeignKey(
        'inventory.StockMovement', null=True, blank=True, editable=False,
        on_delete=models.SET_NULL, related_name='+',
        help_text=_('The Silage/Hay inventory usage this record produced.')
    )
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='feeding_records'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('block', 'date', 'session')
        ordering = ['-date', 'session']

    def __str__(self):
        return f'{self.block.name} - {self.date} {self.session}'


class FeedingRecordCow(models.Model):
    """Per-cow feed allocation within a FeedingRecord. Defaults to an even
    split of the block totals across the cows selected (see
    cows.views._sync_feeding_cows) - a farmer who doesn't care about
    per-cow precision never has to think about this model. Overriding
    individual amounts is what makes per-cow feed-milk correlation and the
    prediction model's feed feature real rather than an estimate."""

    feeding_record = models.ForeignKey(FeedingRecord, on_delete=models.CASCADE, related_name='allocations')
    cow = models.ForeignKey(Cow, on_delete=models.CASCADE, related_name='feeding_allocations')
    dairy_meal_kg = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('0'))
    silage_hay_kg = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('0'))

    class Meta:
        unique_together = ('feeding_record', 'cow')

    def __str__(self):
        return f'{self.cow.tag_id} @ {self.feeding_record}'


class MilkRecord(models.Model):
    farm = models.ForeignKey('farms.Farm', on_delete=models.CASCADE, related_name='milk_records')
    cow = models.ForeignKey(
        Cow, on_delete=models.CASCADE, related_name='milk_records'
    )
    block = models.ForeignKey(
        'farms.Block', on_delete=models.CASCADE, related_name='milk_records',
        help_text=_("Snapshot of the cow's block at the time of recording.")
    )
    date = models.DateField()
    session = models.CharField(max_length=4, choices=Session.choices)
    recorded_time = models.TimeField(
        null=True, blank=True,
        help_text=_('The actual time of day this was recorded - determines the session (AM/Noon/Evening).')
    )
    liters = models.DecimalField(max_digits=7, decimal_places=2, default=Decimal('0'))
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='milk_records'
    )
    stock_movement = models.ForeignKey(
        'inventory.StockMovement', null=True, blank=True, editable=False,
        on_delete=models.SET_NULL, related_name='+',
        help_text=_(
            'The Milk inventory restock this record produced - kept so editing/deleting '
            'the record can reconcile that stock movement instead of leaving it stale.'
        )
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('cow', 'date', 'session')
        ordering = ['-date', 'session']

    def __str__(self):
        return f'{self.cow.tag_id} - {self.date} {self.session} - {self.liters}L'
