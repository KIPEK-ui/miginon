from django import forms
from django.utils.translation import gettext_lazy as _

from core.formhelpers import TailwindFormMixin
from farms.models import FarmMembership

from .models import Task


class TaskForm(TailwindFormMixin, forms.ModelForm):
    class Meta:
        model = Task
        fields = ['title', 'description', 'assigned_to', 'block', 'crop', 'priority', 'due_date']
        widgets = {
            'title': forms.TextInput(attrs={'placeholder': _('e.g. Clean Block A trough')}),
            'description': forms.TextInput(attrs={'placeholder': _('Optional notes')}),
            'due_date': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, farm=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['assigned_to'].required = True
        self.fields['assigned_to'].label = _('Assign to')
        self.fields['block'].label = _('Block (optional)')
        self.fields['crop'].label = _('Crop (optional)')
        if farm is not None:
            self.fields['assigned_to'].queryset = farm.memberships.filter(
                status=FarmMembership.Status.ACTIVE
            ).select_related('user')
            self.fields['block'].queryset = farm.blocks.all()
            self.fields['crop'].queryset = farm.crops.all()
