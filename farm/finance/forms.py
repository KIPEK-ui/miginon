from django import forms

from core.formhelpers import TailwindFormMixin

from .models import Transaction


class TransactionForm(TailwindFormMixin, forms.ModelForm):
    class Meta:
        model = Transaction
        fields = ['kind', 'category', 'amount', 'date', 'note']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'note': forms.TextInput(attrs={'placeholder': 'Optional'}),
        }


class MilkSaleForm(TailwindFormMixin, forms.Form):
    date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    liters = forms.DecimalField(max_digits=7, decimal_places=2, min_value=0.01, label='Liters sold')
    amount = forms.DecimalField(max_digits=10, decimal_places=2, min_value=0.01, label='Amount received')
    note = forms.CharField(required=False, widget=forms.TextInput(attrs={'placeholder': 'Optional, e.g. buyer name'}))
