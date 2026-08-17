from django import forms

from core.formhelpers import SELECT_CLASSES, TailwindFormMixin

from .kenya_data import ALL_TOWN_CHOICES, COUNTY_TOWNS, KENYA_COUNTY_CHOICES
from .models import Block, Farm, FarmRole

KENYA = 'KE'


class KenyaLocationFieldsMixin:
    """Adds Country -> County -> Location fields (in that order) to a plain
    (non-Model) form. The app only supports Kenya for now, so Country is
    fixed (a hidden field, not a dropdown) rather than pretend to be
    editable. Location's choices span every town, and JS
    (see partials/kenya_location_fields.html) narrows the visible options
    to the selected county - that's just a client-side convenience, so
    clean() re-checks the pairing is valid server-side too."""

    def add_location_fields(self):
        self.fields['country'] = forms.CharField(
            initial=KENYA, widget=forms.HiddenInput(), required=False,
        )
        self.fields['county'] = forms.ChoiceField(
            choices=KENYA_COUNTY_CHOICES, label='County', initial='Uasin Gishu',
            widget=forms.Select(attrs={'class': SELECT_CLASSES}),
        )
        self.fields['location'] = forms.ChoiceField(
            choices=ALL_TOWN_CHOICES, label='Nearest town', initial='Eldoret',
            widget=forms.Select(attrs={'class': SELECT_CLASSES}),
        )
        # These were added after TailwindFormMixin's own __init__ already
        # ran its styling pass, so the widget class had to be set above by
        # hand; this just fixes field display order (name field first).
        others = [f for f in self.fields if f not in ('country', 'county', 'location')]
        self.order_fields(['country', 'county', 'location', *others])

    def clean_country(self):
        # Not user-editable - always Kenya, regardless of what a tampered
        # request sends.
        return KENYA

    def clean(self):
        cleaned = super().clean()
        county = cleaned.get('county')
        location = cleaned.get('location')
        if county and location and location not in COUNTY_TOWNS.get(county, []):
            self.add_error(
                'location',
                f'{location} is not listed under {county}. Pick a town from the dropdown for your county.'
            )
        return cleaned


class FarmForm(TailwindFormMixin, KenyaLocationFieldsMixin, forms.Form):
    farm_name = forms.CharField(label='Farm name', max_length=150, widget=forms.TextInput(
        attrs={'placeholder': 'e.g. Miginon Dairy Farm'}
    ))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_location_fields()


class FarmSettingsForm(TailwindFormMixin, forms.ModelForm):
    country = forms.CharField(initial=KENYA, widget=forms.HiddenInput(), required=False)
    county = forms.ChoiceField(
        choices=KENYA_COUNTY_CHOICES, label='County', initial='Uasin Gishu',
    )
    location = forms.ChoiceField(choices=ALL_TOWN_CHOICES, label='Nearest town', initial='Eldoret')

    class Meta:
        model = Farm
        fields = ['name', 'country', 'county', 'location']

    def clean_country(self):
        return KENYA

    def clean(self):
        cleaned = super().clean()
        county = cleaned.get('county')
        location = cleaned.get('location')
        if county and location and location not in COUNTY_TOWNS.get(county, []):
            self.add_error(
                'location',
                f'{location} is not listed under {county}. Pick a town from the dropdown for your county.'
            )
        return cleaned


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
