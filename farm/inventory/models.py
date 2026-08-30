from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class InventoryItem(models.Model):
    class Category(models.TextChoices):
        FEED = 'feed', _('Feed')
        VETERINARY = 'veterinary', _('Veterinary & Medicine')
        EQUIPMENT = 'equipment', _('Equipment')
        PRODUCE = 'produce', _('Produce')
        OTHER = 'other', _('Other')

    class Unit(models.TextChoices):
        KG = 'kg', _('Kilograms')
        LITRES = 'l', _('Litres')
        BAGS = 'bags', _('Bags')
        PIECES = 'pcs', _('Pieces')
        BOXES = 'boxes', _('Boxes')

    farm = models.ForeignKey('farms.Farm', on_delete=models.CASCADE, related_name='inventory_items')
    name = models.CharField(max_length=100)
    category = models.CharField(max_length=15, choices=Category.choices, default=Category.OTHER)
    unit = models.CharField(max_length=10, choices=Unit.choices, default=Unit.KG)
    current_stock = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'))
    reorder_level = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0'),
        help_text=_('Get a low-stock warning at or below this level. Leave at 0 to disable.')
    )
    added_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='added_inventory_items'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('farm', 'name')
        ordering = ['name']

    def __str__(self):
        return f'{self.name} ({self.farm.name})'

    @property
    def is_low_stock(self):
        return self.reorder_level > 0 and self.current_stock <= self.reorder_level


class StockMovement(models.Model):
    class MovementType(models.TextChoices):
        RESTOCK = 'in', _('Restock (in)')
        USAGE = 'out', _('Usage (out)')
        ADJUSTMENT = 'adjust', _('Correction')

    farm = models.ForeignKey('farms.Farm', on_delete=models.CASCADE, related_name='stock_movements')
    item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE, related_name='movements')
    date = models.DateField()
    movement_type = models.CharField(max_length=10, choices=MovementType.choices)
    quantity = models.DecimalField(
        max_digits=10, decimal_places=2,
        help_text=_('For a correction, this is the new stock level. Otherwise the amount moved.')
    )
    stock_before = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0'), editable=False,
        help_text=_('Snapshot of current_stock right before this movement was applied.')
    )
    note = models.CharField(max_length=255, blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='stock_movements'
    )
    used_by = models.ForeignKey(
        'farms.FarmMembership', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='equipment_usage',
        help_text=_('Who used/consumed this (most relevant for equipment) - separate from '
                    'recorded_by, who logged the entry.')
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f'{self.item.name} - {self.get_movement_type_display()} - {self.quantity}'


class FeedComposition(models.Model):
    """Ingredient breakdown + crude protein % for a feed item (typically the
    auto-created 'Dairy Meal' item, see inventory.services.record_feed_usage)
    - entered by hand, or pre-filled from inventory.feed_reference's
    rule-based suggestion and then edited/confirmed. Used as a feature by
    the production analytics/prediction models (see analysis.ml)."""

    item = models.OneToOneField(InventoryItem, on_delete=models.CASCADE, related_name='composition')
    ingredients = models.JSONField(default=list, blank=True, help_text=_('List of {"name": ..., "percent": ...}.'))
    crude_protein_pct = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True, help_text=_('Overall crude protein %, e.g. 16.0')
    )
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'Composition for {self.item.name}'
