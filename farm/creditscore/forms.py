from django import forms
from django.utils.translation import gettext_lazy as _l

from core.formhelpers import TailwindFormMixin

from .models import DataPartner


class PartnerApplicationForm(TailwindFormMixin, forms.ModelForm):
    """Public self-serve application for read-only credit-score API access.
    Deliberately excludes slug/api_key/status - those are filled in by
    DataPartner.save() and the admin approval action, never by the
    applicant (see DataPartner's docstring for why approval is a separate,
    human step)."""

    class Meta:
        model = DataPartner
        fields = ['name', 'contact_name', 'contact_email']
        labels = {
            'name': _l('Organization name'),
            'contact_name': _l('Your name'),
            'contact_email': _l('Work email'),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # contact_email is blank=True on the model (a partner created
        # directly in admin doesn't need one), but the application form is
        # useless without a way to deliver the API key once approved.
        self.fields['contact_email'].required = True

    def clean_contact_email(self):
        return self.cleaned_data['contact_email'].strip().lower()
