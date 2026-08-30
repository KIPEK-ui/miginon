from django import forms
from django.utils.translation import gettext_lazy as _

from core.formhelpers import TailwindFormMixin

from .models import Crop, CropActivity


class CropForm(TailwindFormMixin, forms.ModelForm):
    class Meta:
        model = Crop
        fields = ['name', 'field_name', 'status', 'planted_on', 'expected_harvest']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': _('e.g. Napier grass')}),
            'field_name': forms.TextInput(attrs={'placeholder': _('e.g. North field')}),
            'planted_on': forms.DateInput(attrs={'type': 'date'}),
            'expected_harvest': forms.DateInput(attrs={'type': 'date'}),
        }


class CropActivityForm(TailwindFormMixin, forms.ModelForm):
    class Meta:
        model = CropActivity
        fields = ['crop', 'date', 'activity_type', 'quantity_harvested_kg', 'notes']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.TextInput(attrs={'placeholder': _('Optional')}),
        }

    def __init__(self, *args, farm=None, **kwargs):
        super().__init__(*args, **kwargs)
        if farm is not None:
            self.fields['crop'].queryset = farm.crops.all()
