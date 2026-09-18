import json

from django import forms
from django.utils.translation import gettext_lazy as _

from core.formhelpers import TailwindFormMixin
from farms.models import Block

from .models import LandParcel
from .services import area_sqm, perimeter_m


class LandParcelForm(TailwindFormMixin, forms.ModelForm):
    coordinates_json = forms.CharField(widget=forms.HiddenInput)

    class Meta:
        model = LandParcel
        fields = ['name', 'block']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': _('e.g. North boundary, Maize field')}),
        }

    def __init__(self, *args, farm=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.farm = farm
        self.fields['block'].queryset = Block.objects.filter(farm=farm)
        self.fields['block'].required = False

    def clean_coordinates_json(self):
        raw = self.cleaned_data['coordinates_json']
        try:
            coords = json.loads(raw)
        except ValueError:
            raise forms.ValidationError(_('Invalid shape data.'))
        if not isinstance(coords, list) or len(coords) < 3:
            raise forms.ValidationError(_('Draw at least 3 points before saving.'))
        cleaned = []
        for point in coords:
            if not (isinstance(point, list) and len(point) == 2):
                raise forms.ValidationError(_('Invalid shape data.'))
            lng, lat = point
            try:
                lng, lat = float(lng), float(lat)
            except (TypeError, ValueError):
                raise forms.ValidationError(_('Invalid shape data.'))
            if not (-180 <= lng <= 180 and -90 <= lat <= 90):
                raise forms.ValidationError(_('Invalid shape data.'))
            cleaned.append([lng, lat])
        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.farm = self.farm
        coords = self.cleaned_data['coordinates_json']
        instance.coordinates = coords
        instance.area_sqm = round(area_sqm(coords), 2)
        instance.perimeter_m = round(perimeter_m(coords), 2)
        if commit:
            instance.save()
        return instance
