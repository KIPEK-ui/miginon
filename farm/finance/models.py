from django.conf import settings
from django.db import models


class Transaction(models.Model):
    class Kind(models.TextChoices):
        INCOME = 'income', 'Income'
        EXPENSE = 'expense', 'Expense'

    class Category(models.TextChoices):
        FEED = 'feed', 'Feed & Nutrition'
        VETERINARY = 'veterinary', 'Veterinary'
        LABOR = 'labor', 'Labor / Wages'
        EQUIPMENT = 'equipment', 'Equipment'
        TRANSPORT = 'transport', 'Transport'
        UTILITIES = 'utilities', 'Utilities'
        WATER = 'water', 'Water'
        FUEL = 'fuel', 'Fuel'
        SALES = 'sales', 'Produce Sales'
        OTHER = 'other', 'Other'

    farm = models.ForeignKey('farms.Farm', on_delete=models.CASCADE, related_name='transactions')
    kind = models.CharField(max_length=10, choices=Kind.choices)
    category = models.CharField(max_length=15, choices=Category.choices, default=Category.OTHER)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    date = models.DateField()
    note = models.CharField(max_length=255, blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='transactions'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f'{self.get_kind_display()} - {self.amount} - {self.farm.name}'
