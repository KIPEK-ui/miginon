from django import forms
from django.utils.translation import gettext_lazy as _

from core.formhelpers import TailwindFormMixin
from inventory.models import InventoryItem

from .models import RESERVED_SLUGS, FarmSite, Order, Product, SitePage


class FarmSiteForm(TailwindFormMixin, forms.ModelForm):
    class Meta:
        model = FarmSite
        fields = ['slug', 'tagline', 'theme', 'is_published']
        widgets = {
            'slug': forms.TextInput(attrs={'placeholder': _('e.g. green-valley-farm')}),
            'tagline': forms.TextInput(attrs={'placeholder': _('e.g. Certified dairy, Uasin Gishu')}),
        }

    def clean_slug(self):
        slug = self.cleaned_data['slug'].strip().lower()
        if slug in RESERVED_SLUGS:
            raise forms.ValidationError(_('That address is reserved - try another.'))
        conflict = FarmSite.objects.filter(slug=slug).exclude(pk=self.instance.pk)
        if conflict.exists():
            raise forms.ValidationError(_('That address is already taken - try another.'))
        return slug


class SitePageForm(TailwindFormMixin, forms.ModelForm):
    class Meta:
        model = SitePage
        fields = [
            'title', 'slug', 'template', 'headline', 'subheading', 'body',
            'image', 'image_url', 'cta_label', 'cta_url', 'contact_phone', 'contact_email', 'order',
        ]
        widgets = {
            'title': forms.TextInput(attrs={'placeholder': _('e.g. Home, About us, Contact')}),
            'slug': forms.TextInput(attrs={'placeholder': _('Leave blank for the homepage')}),
            'headline': forms.TextInput(attrs={'placeholder': _('The big line visitors see first')}),
            'subheading': forms.TextInput(attrs={'placeholder': _('Optional supporting line')}),
            'body': forms.Textarea(attrs={'rows': 6}),
            'image': forms.ClearableFileInput(attrs={'accept': 'image/*'}),
            'image_url': forms.URLInput(attrs={'placeholder': 'https://...'}),
            'cta_label': forms.TextInput(attrs={'placeholder': _('e.g. Contact us')}),
            'cta_url': forms.URLInput(attrs={'placeholder': 'https://...'}),
            'contact_phone': forms.TextInput(attrs={'placeholder': '+254 7...'}),
        }

    def __init__(self, *args, site=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._site = site

    def clean_slug(self):
        from django.utils.text import slugify
        slug = slugify(self.cleaned_data.get('slug', ''))
        site = self._site or (self.instance.site_id and self.instance.site)
        if site is not None:
            conflict = SitePage.objects.filter(site=site, slug=slug).exclude(pk=self.instance.pk)
            if conflict.exists():
                raise forms.ValidationError(
                    _('This farm already has a page at that address.') if slug
                    else _('This farm already has a homepage - only one page can be blank.')
                )
        return slug


class ProductForm(TailwindFormMixin, forms.ModelForm):
    class Meta:
        model = Product
        fields = ['name', 'inventory_item', 'description', 'price', 'unit', 'image', 'is_available']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': _('e.g. Fresh farm milk')}),
            'description': forms.TextInput(attrs={'placeholder': _('Optional')}),
            'unit': forms.TextInput(attrs={'placeholder': _('e.g. per liter, per kg, per dozen')}),
            'image': forms.ClearableFileInput(attrs={'accept': 'image/*'}),
        }

    def __init__(self, *args, farm=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['inventory_item'].required = False
        self.fields['inventory_item'].queryset = (
            InventoryItem.objects.filter(farm=farm, category=InventoryItem.Category.PRODUCE) if farm is not None
            else InventoryItem.objects.none()
        )


class OrderEnquiryForm(TailwindFormMixin, forms.ModelForm):
    # A field no real visitor sees or fills in (hidden off-screen by the
    # public template's CSS, not merely a hidden input type) - a submission
    # that has it filled in is almost certainly a bot, so it's accepted
    # (200, no error revealing the trap) but silently dropped rather than
    # creating an Order. See website.views.order_create.
    website = forms.CharField(required=False, widget=forms.TextInput(attrs={'autocomplete': 'off', 'tabindex': '-1'}))

    class Meta:
        model = Order
        fields = ['quantity', 'buyer_name', 'buyer_phone', 'buyer_note']
        widgets = {
            'buyer_name': forms.TextInput(attrs={'placeholder': _('Your name')}),
            'buyer_phone': forms.TextInput(attrs={'placeholder': _('Phone number')}),
            'buyer_note': forms.TextInput(attrs={'placeholder': _('Optional')}),
        }
