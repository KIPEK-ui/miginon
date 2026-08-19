from django import forms

from core.formhelpers import OTP_INPUT_CLASSES, TailwindFormMixin
from farms.forms import KenyaLocationFieldsMixin


class FarmCodeForm(TailwindFormMixin, forms.Form):
    code = forms.CharField(
        label='Farm ID',
        max_length=8,
        min_length=6,
        widget=forms.TextInput(attrs={
            'placeholder': 'e.g. GR7K9QAB',
            'class': 'w-full rounded-xl border border-stone-300 bg-white px-4 py-3 text-center '
                     'text-lg tracking-[0.3em] font-semibold uppercase text-stone-900 '
                     'placeholder-stone-400 focus:border-emerald-600 focus:ring-2 '
                     'focus:ring-emerald-100 focus:outline-none transition',
            'autocapitalize': 'characters',
        }),
    )

    def clean_code(self):
        return self.cleaned_data['code'].strip().upper()


class EmailLoginForm(TailwindFormMixin, forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'placeholder': 'you@example.com'})
    )

    def clean_email(self):
        return self.cleaned_data['email'].strip().lower()


class OTPForm(TailwindFormMixin, forms.Form):
    code = forms.CharField(
        label='6-digit code',
        max_length=6,
        min_length=6,
        widget=forms.TextInput(attrs={
            'placeholder': '000000',
            'class': OTP_INPUT_CLASSES,
            'inputmode': 'numeric',
            'autocomplete': 'one-time-code',
        }),
    )

    def clean_code(self):
        code = self.cleaned_data['code'].strip()
        if not code.isdigit():
            raise forms.ValidationError('Enter the 6-digit numeric code.')
        return code


class SignupAccountForm(TailwindFormMixin, forms.Form):
    first_name = forms.CharField(max_length=60)
    last_name = forms.CharField(max_length=60, required=False)
    email = forms.EmailField()
    phone = forms.CharField(max_length=20, required=False, widget=forms.TextInput(
        attrs={'placeholder': '07XX XXX XXX'}
    ))

    def clean_email(self):
        from .models import User
        email = self.cleaned_data['email'].strip().lower()
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError(
                'An account with this email already exists. Try logging in instead.'
            )
        return email


class SignupFarmForm(TailwindFormMixin, KenyaLocationFieldsMixin, forms.Form):
    farm_name = forms.CharField(label='Farm name', max_length=150, widget=forms.TextInput(
        attrs={'placeholder': 'e.g. Miginon Dairy Farm'}
    ))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_location_fields()


class ProfileForm(TailwindFormMixin, forms.ModelForm):
    class Meta:
        from .models import User
        model = User
        fields = ['first_name', 'last_name', 'phone']
        widgets = {
            'phone': forms.TextInput(attrs={'placeholder': '07XX XXX XXX'}),
        }


class NotificationPreferenceForm(TailwindFormMixin, forms.ModelForm):
    class Meta:
        from .models import User
        model = User
        fields = ['notification_delivery']
        labels = {'notification_delivery': 'Notify me via'}


class EmailChangeForm(TailwindFormMixin, forms.Form):
    new_email = forms.EmailField(label='New email address')

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def clean_new_email(self):
        from .models import User
        email = self.cleaned_data['new_email'].strip().lower()
        if self.user and email == self.user.email:
            raise forms.ValidationError('That is already your current email address.')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('An account with this email already exists.')
        return email
