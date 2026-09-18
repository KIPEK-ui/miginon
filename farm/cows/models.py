from datetime import time, timedelta
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

GESTATION_DAYS = 283
TARGET_DRY_PERIOD_DAYS = 60
ESTRUS_CYCLE_DAYS = 21


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
    sire = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.SET_NULL, related_name='sired_calves',
        limit_choices_to={'gender': Gender.MALE},
        help_text=_('If the sire is in this herd. Otherwise use "External sire" below.')
    )
    dam = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.SET_NULL, related_name='calves',
        limit_choices_to={'gender': Gender.FEMALE},
    )
    sire_name = models.CharField(
        max_length=100, blank=True,
        help_text=_('External or AI bull not recorded in this herd, e.g. an AI code or name.')
    )
    registration_number = models.CharField(
        max_length=60, blank=True, help_text=_('Breed society / pedigree registration number, if registered.')
    )
    notes = models.CharField(max_length=255, blank=True)
    added_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='added_cows'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    hedera_token_id = models.CharField(max_length=20, blank=True)
    hedera_serial_number = models.PositiveIntegerField(null=True, blank=True)
    hedera_transaction_id = models.CharField(max_length=40, blank=True)
    hedera_minted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('farm', 'tag_id')
        ordering = ['tag_id']

    def __str__(self):
        return self.name or self.tag_id

    @property
    def days_in_milk(self):
        if not self.last_calving_date:
            return None
        return (timezone.localdate() - self.last_calving_date).days

    def latest_reproductive_event(self, event_types=None):
        events = self.reproductive_events.all()
        if event_types:
            events = events.filter(event_type__in=event_types)
        return events.first()

    @property
    def expected_calving_date(self):
        """Due date estimated from the most recent insemination/confirmed
        pregnancy - None once a later calving/open/abortion event shows
        that pregnancy didn't carry through (or never confirmed one)."""
        conception = self.latest_reproductive_event(
            [ReproductiveEvent.EventType.INSEMINATION, ReproductiveEvent.EventType.PREGNANCY_CONFIRMED]
        )
        if not conception:
            return None
        resolved = self.latest_reproductive_event([
            ReproductiveEvent.EventType.CALVED,
            ReproductiveEvent.EventType.PREGNANCY_NEGATIVE,
            ReproductiveEvent.EventType.ABORTED,
        ])
        if resolved and resolved.date >= conception.date:
            return None
        return conception.date + timedelta(days=GESTATION_DAYS)

    @property
    def expected_dry_off_date(self):
        due = self.expected_calving_date
        if not due:
            return None
        return due - timedelta(days=TARGET_DRY_PERIOD_DAYS)

    @property
    def next_heat_expected(self):
        """Only meaningful while not already confirmed pregnant since - a
        pregnant cow doesn't cycle again until after calving."""
        if self.expected_calving_date:
            return None
        heat = self.latest_reproductive_event([ReproductiveEvent.EventType.HEAT])
        if not heat:
            return None
        return heat.date + timedelta(days=ESTRUS_CYCLE_DAYS)


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


class CowHealthRecord(models.Model):
    """A vaccination/treatment/checkup logged against one cow - makes the
    advisory app's disease catalog actionable (a farm's own clinical
    history) rather than only reference material. Not every entry maps to
    a cataloged disease (a routine vaccination usually doesn't), so
    `disease` is optional."""

    class RecordType(models.TextChoices):
        VACCINATION = 'vaccination', _('Vaccination')
        TREATMENT = 'treatment', _('Treatment')
        CHECKUP = 'checkup', _('Checkup')
        OTHER = 'other', _('Other')

    farm = models.ForeignKey('farms.Farm', on_delete=models.CASCADE, related_name='cow_health_records')
    cow = models.ForeignKey(Cow, on_delete=models.CASCADE, related_name='health_records')
    disease = models.ForeignKey(
        'advisory.DiseaseCatalog', null=True, blank=True, on_delete=models.SET_NULL, related_name='+',
        help_text=_('Optional - link the matching advisory catalog entry if this was for a known disease.')
    )
    record_type = models.CharField(max_length=15, choices=RecordType.choices)
    description = models.CharField(max_length=255)
    date = models.DateField()
    next_due_date = models.DateField(
        null=True, blank=True, help_text=_('For a follow-up dose/checkup, if there is one.')
    )
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='cow_health_records'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f'{self.cow.tag_id} - {self.get_record_type_display()} - {self.date}'


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


class CowWeightRecord(models.Model):
    class Method(models.TextChoices):
        SCALE = 'scale', _('Weighbridge/scale')
        TAPE = 'tape', _('Heart-girth tape')
        VISUAL = 'visual', _('Visual estimate')

    farm = models.ForeignKey('farms.Farm', on_delete=models.CASCADE, related_name='cow_weight_records')
    cow = models.ForeignKey(Cow, on_delete=models.CASCADE, related_name='weight_records')
    date = models.DateField()
    method = models.CharField(max_length=10, choices=Method.choices, default=Method.TAPE)
    heart_girth_cm = models.DecimalField(
        max_digits=5, decimal_places=1, null=True, blank=True,
        help_text=_(
            'Tape measurement around the chest, just behind the front legs. Leave weight below blank to '
            'estimate it from this measurement.'
        )
    )
    weight_kg = models.DecimalField(
        max_digits=6, decimal_places=1,
        help_text=_('Enter directly from a scale, or leave blank to estimate from the tape measurement above.')
    )
    body_condition_score = models.DecimalField(
        max_digits=2, decimal_places=1, null=True, blank=True,
        help_text=_('1 (emaciated) to 5 (obese), in 0.25 steps.')
    )
    notes = models.CharField(max_length=255, blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='cow_weight_records'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('cow', 'date')
        ordering = ['-date']

    def __str__(self):
        return f'{self.cow.tag_id} - {self.date} - {self.weight_kg}kg'


class ReproductiveEvent(models.Model):
    """One entry in a cow's breeding calendar. Cow.expected_calving_date /
    expected_dry_off_date / next_heat_expected are all computed from these
    rather than stored, so there's nothing to keep in sync by hand - and
    cow.status/last_calving_date are updated by the view when a 'calved' or
    'dry_off' event is logged (see cows.views.reproduction_create)."""

    class EventType(models.TextChoices):
        HEAT = 'heat', _('Heat observed')
        INSEMINATION = 'insemination', _('Service / Insemination')
        PREGNANCY_CONFIRMED = 'pregnant', _('Pregnancy confirmed')
        PREGNANCY_NEGATIVE = 'open', _('Pregnancy check - not in calf')
        DRY_OFF = 'dry_off', _('Dried off')
        CALVED = 'calved', _('Calved')
        ABORTED = 'aborted', _('Abortion / loss')

    farm = models.ForeignKey('farms.Farm', on_delete=models.CASCADE, related_name='reproductive_events')
    cow = models.ForeignKey(Cow, on_delete=models.CASCADE, related_name='reproductive_events')
    event_type = models.CharField(max_length=15, choices=EventType.choices)
    date = models.DateField()
    sire = models.ForeignKey(
        Cow, null=True, blank=True, on_delete=models.SET_NULL, related_name='+',
        limit_choices_to={'gender': Cow.Gender.MALE},
        help_text=_('For a Service/Insemination event, if the bull is in this herd.')
    )
    sire_name = models.CharField(
        max_length=100, blank=True,
        help_text=_('External or AI bull, e.g. an AI code or name - used instead of/alongside the field above.')
    )
    notes = models.CharField(max_length=255, blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='reproductive_events'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f'{self.cow.tag_id} - {self.get_event_type_display()} - {self.date}'
