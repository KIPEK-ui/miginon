from django import forms

from core.formhelpers import TailwindFormMixin

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
        fields = ['item', 'date', 'movement_type', 'quantity', 'note']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'note': forms.TextInput(attrs={'placeholder': 'Optional'}),
        }

    def __init__(self, *args, farm=None, **kwargs):
        super().__init__(*args, **kwargs)
        if farm is not None:
            self.fields['item'].queryset = farm.inventory_items.all()
