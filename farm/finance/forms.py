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
