from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class Crop(models.Model):
    class Status(models.TextChoices):
        PLANNED = 'planned', _('Planned')
        GROWING = 'growing', _('Growing')
        HARVESTED = 'harvested', _('Harvested')

    farm = models.ForeignKey('farms.Farm', on_delete=models.CASCADE, related_name='crops')
    name = models.CharField(max_length=100)
    field_name = models.CharField(
        max_length=100, blank=True,
        help_text=_('Free-text label - used only when this crop has no mapped land_parcel below.')
    )
    land_parcel = models.ForeignKey(
        'geomap.LandParcel', null=True, blank=True, on_delete=models.SET_NULL, related_name='crops',
        help_text=_('A GPS-mapped field from GeoMap, if this crop has one - preferred over field_name when set.')
    )
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PLANNED)
    planted_on = models.DateField(null=True, blank=True)
    expected_harvest = models.DateField(null=True, blank=True)
    added_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='added_crops'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.name} - {self.farm.name}'

    @property
    def field_label(self):
        """The GPS-mapped parcel's name when this crop has one, else the
        free-text field_name, else nothing - the parcel is authoritative
        when both are somehow set."""
        if self.land_parcel_id:
            return self.land_parcel.name
        return self.field_name


class CropActivity(models.Model):
    class ActivityType(models.TextChoices):
        PLANTING = 'planting', _('Planting')
        WEEDING = 'weeding', _('Weeding')
        SPRAYING = 'spraying', _('Spraying')
        FERTILIZING = 'fertilizing', _('Fertilizing')
        HARVESTING = 'harvesting', _('Harvesting')
        OTHER = 'other', _('Other')

    farm = models.ForeignKey('farms.Farm', on_delete=models.CASCADE, related_name='crop_activities')
    crop = models.ForeignKey(Crop, on_delete=models.CASCADE, related_name='activities')
    date = models.DateField()
    activity_type = models.CharField(max_length=15, choices=ActivityType.choices)
    quantity_harvested_kg = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        help_text=_('Only relevant for a harvesting activity')
    )
    notes = models.CharField(max_length=255, blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='crop_activities'
    )
    stock_movement = models.ForeignKey(
        'inventory.StockMovement', null=True, blank=True, editable=False,
        on_delete=models.SET_NULL, related_name='+',
        help_text=_('The produce inventory restock this harvesting activity produced.')
    )
    created_at = models.DateTimeField(auto_now_add=True)
    hedera_token_id = models.CharField(max_length=20, blank=True)
    hedera_serial_number = models.PositiveIntegerField(null=True, blank=True)
    hedera_transaction_id = models.CharField(max_length=40, blank=True)
    hedera_minted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-date', '-created_at']
        verbose_name_plural = 'Crop activities'

    def __str__(self):
        return f'{self.crop.name} - {self.get_activity_type_display()} - {self.date}'
