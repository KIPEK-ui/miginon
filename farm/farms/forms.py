from django import forms

from core.formhelpers import TailwindFormMixin

from .models import Block, Farm, FarmRole


class FarmForm(TailwindFormMixin, forms.Form):
    farm_name = forms.CharField(label='Farm name', max_length=150, widget=forms.TextInput(
        attrs={'placeholder': 'e.g. Miginon Dairy Farm'}
    ))
    location = forms.CharField(max_length=200, required=False, widget=forms.TextInput(
        attrs={'placeholder': 'e.g. Eldoret, Uasin Gishu'}
    ))
    county = forms.CharField(max_length=100, required=False)


class FarmSettingsForm(TailwindFormMixin, forms.ModelForm):
    class Meta:
        model = Farm
        fields = ['name', 'location', 'county']


class BlockForm(TailwindFormMixin, forms.ModelForm):
    class Meta:
        model = Block
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'e.g. Block A'}),
            'description': forms.TextInput(attrs={'placeholder': 'Optional notes about this block'}),
        }


class WorkerInviteForm(TailwindFormMixin, forms.Form):
    first_name = forms.CharField(max_length=60)
    last_name = forms.CharField(max_length=60, required=False)
    email = forms.EmailField()
    role = forms.ChoiceField(choices=[])

    def __init__(self, *args, assignable_roles=None, **kwargs):
        super().__init__(*args, **kwargs)
        roles = assignable_roles or [FarmRole.MANAGER, FarmRole.SUPERVISOR, FarmRole.WORKER]
        self.fields['role'].choices = [(r.value, r.label) for r in roles]

    def clean_email(self):
        return self.cleaned_data['email'].strip().lower()


class WorkerRoleForm(TailwindFormMixin, forms.Form):
    role = forms.ChoiceField(choices=[])

    def __init__(self, *args, assignable_roles=None, **kwargs):
        super().__init__(*args, **kwargs)
        roles = assignable_roles or [FarmRole.MANAGER, FarmRole.SUPERVISOR, FarmRole.WORKER]
        self.fields['role'].choices = [(r.value, r.label) for r in roles]
