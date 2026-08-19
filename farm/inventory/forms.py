from django import forms

from core.formhelpers import TailwindFormMixin
from farms.models import FarmMembership

from .models import InventoryItem, StockMovement


class InventoryItemForm(TailwindFormMixin, forms.ModelForm):
    class Meta:
        model = InventoryItem
        fields = ['name', 'category', 'unit', 'current_stock', 'reorder_level']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'e.g. Dairy meal'}),
        }

    def __init__(self, *args, lock_stock=False, **kwargs):
        super().__init__(*args, **kwargs)
        if lock_stock:
            # Once an item exists, its stock only moves through logged
            # StockMovement entries, so the running total stays auditable.
            del self.fields['current_stock']


class StockMovementForm(TailwindFormMixin, forms.ModelForm):
    class Meta:
        model = StockMovement
        fields = ['item', 'date', 'movement_type', 'quantity', 'used_by', 'note']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'note': forms.TextInput(attrs={'placeholder': 'Optional'}),
        }
        labels = {'used_by': 'Used by (optional)'}

    def __init__(self, *args, farm=None, **kwargs):
        super().__init__(*args, **kwargs)
        if farm is not None:
            self.fields['item'].queryset = farm.inventory_items.all()
            self.fields['used_by'].queryset = farm.memberships.filter(
                status=FarmMembership.Status.ACTIVE
            ).select_related('user')


class MilkUsageForm(TailwindFormMixin, forms.Form):
    PURPOSE_CHOICES = [
        ('calf', 'Calf feeding'),
        ('staff', 'Staff consumption'),
        ('other', 'Other internal use'),
    ]

    date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    liters = forms.DecimalField(max_digits=7, decimal_places=2, min_value=0.01, label='Liters used')
    purpose = forms.ChoiceField(choices=PURPOSE_CHOICES)
    used_by = forms.ModelChoiceField(
        queryset=FarmMembership.objects.none(), required=False, label='Staff member (if applicable)'
    )
    note = forms.CharField(
        required=False, widget=forms.TextInput(attrs={'placeholder': 'Optional, e.g. which calves'})
    )

    def __init__(self, *args, farm=None, **kwargs):
        super().__init__(*args, **kwargs)
        if farm is not None:
            self.fields['used_by'].queryset = farm.memberships.filter(
                status=FarmMembership.Status.ACTIVE
            ).select_related('user')
