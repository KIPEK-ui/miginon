from django import forms

from core.formhelpers import TailwindFormMixin
from farms.models import Block

from .models import Cow, FeedingRecord, MilkRecord


class CowForm(TailwindFormMixin, forms.ModelForm):
    class Meta:
        model = Cow
        fields = ['block', 'tag_id', 'name', 'category', 'gender', 'breed', 'date_of_birth', 'last_calving_date', 'status']
        widgets = {
            'tag_id': forms.TextInput(attrs={'placeholder': 'e.g. C-014'}),
            'name': forms.TextInput(attrs={'placeholder': 'Optional'}),
            'breed': forms.TextInput(attrs={'placeholder': 'e.g. Friesian'}),
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
            'last_calving_date': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, farm=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.farm = farm
        if farm is not None:
            self.fields['block'].queryset = farm.blocks.all()

    def clean_tag_id(self):
        # ModelForm's automatic unique_together validation excludes any field
        # not in Meta.fields - since 'farm' isn't a form field, the model's
        # ('farm', 'tag_id') check never fires on its own, and the view sets
        # cow.farm only after is_valid(), so a duplicate would otherwise slip
        # through as a raw IntegrityError at cow.save() instead of a clean
        # form error here.
        tag_id = self.cleaned_data['tag_id'].strip()
        if self.farm is not None:
            existing = Cow.objects.filter(farm=self.farm, tag_id=tag_id)
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                raise forms.ValidationError('A cow with this tag ID already exists on this farm.')
        return tag_id

    def clean(self):
        cleaned = super().clean()
        category = cleaned.get('category')
        gender = cleaned.get('gender')
        if category == Cow.Category.BULL and gender != Cow.Gender.MALE:
            self.add_error('gender', 'A bull must be male.')
        elif category in (Cow.Category.HEIFER, Cow.Category.COW) and gender != Cow.Gender.FEMALE:
            self.add_error('gender', f'A {category} must be female.')
        return cleaned


class CowChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        cow = obj
        label = f'{cow.tag_id} - {cow.name}' if cow.name else cow.tag_id
        return f'{label} ({cow.block.name})'


class FeedingRecordForm(TailwindFormMixin, forms.ModelForm):
    cows = forms.ModelMultipleChoiceField(
        queryset=Cow.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        error_messages={'required': 'Select at least one cow that was fed.'},
    )

    class Meta:
        model = FeedingRecord
        # 'cows' is deliberately NOT listed here even though it's a real
        # field on the model: it's now a ManyToManyField with a custom
        # `through` (FeedingRecordCow, which carries per-cow kg amounts),
        # and Django's ModelForm.save_m2m() can't auto-save a through'd M2M
        # (it raises). The field above still renders/validates cow
        # selection - cows.views._sync_feeding_cows does the actual saving.
        fields = ['block', 'date', 'session', 'dairy_meal_kg', 'silage_hay_kg']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, farm=None, **kwargs):
        super().__init__(*args, **kwargs)
        if farm is not None:
            self.fields['block'].queryset = farm.blocks.all()
            self.fields['block'].empty_label = None
            self.fields['cows'].queryset = (
                farm.cows.filter(status=Cow.Status.ACTIVE).select_related('block').order_by('block__name', 'tag_id')
            )

    def clean(self):
        cleaned = super().clean()
        block = cleaned.get('block')
        cows = cleaned.get('cows')
        if block and cows:
            mismatched = [c for c in cows if c.block_id != block.id]
            if mismatched:
                names = ', '.join(c.tag_id for c in mismatched)
                raise forms.ValidationError(
                    f'{names} does not belong to {block.name}. Pick cows from the selected block only.'
                )
        return cleaned


class MilkRecordForm(TailwindFormMixin, forms.ModelForm):
    cow = CowChoiceField(queryset=Cow.objects.none())

    class Meta:
        model = MilkRecord
        fields = ['cow', 'date', 'session', 'liters']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, farm=None, **kwargs):
        super().__init__(*args, **kwargs)
        if farm is not None:
            self.fields['cow'].queryset = (
                farm.cows.filter(status=Cow.Status.ACTIVE).select_related('block').order_by('block__name', 'tag_id')
            )


class CowTransferForm(TailwindFormMixin, forms.Form):
    to_block = forms.ModelChoiceField(queryset=Block.objects.none(), label='Move to block')
    note = forms.CharField(
        max_length=255, required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Optional reason, e.g. calving, herd rebalancing'})
    )

    def __init__(self, *args, cow=None, **kwargs):
        super().__init__(*args, **kwargs)
        if cow is not None:
            self.fields['to_block'].queryset = cow.farm.blocks.exclude(id=cow.block_id)
