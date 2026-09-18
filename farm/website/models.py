import re

from django.db import models
from django.utils.translation import gettext_lazy as _

# A farm's site now lives directly at "/<slug>/" (see farm/urls.py), so a
# slug matching any other top-level URL prefix would make that farm's site
# unreachable at its own address - silently shadowed by the real app, not a
# crash. Every literal first-path-segment used elsewhere in the project.
RESERVED_SLUGS = frozenset({
    'django-admin', 'admin', 'accounts', 'farm', 'cows', 'crops', 'finance',
    'inventory', 'analysis', 'notifications', 'tasks', 'weather', 'advisory',
    'wallet', 'credit-score', 'website', 'static', 'media', 'theme',
    'language', 'offline', 'robots.txt', 'favicon.ico',
})


def _slugify_base(name):
    slug = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
    return slug or 'farm'


def generate_site_slug(name):
    """First-choice slug, then -2, -3, ... on collision - same pattern as
    farms.models.generate_farm_code, just human-readable since this one is
    public-facing (it's literally the farm's URL) rather than an opaque
    login code. A reserved slug is treated exactly like a taken one."""
    base = _slugify_base(name)[:40]
    slug = base
    n = 2
    while slug in RESERVED_SLUGS or FarmSite.objects.filter(slug=slug).exists():
        suffix = f'-{n}'
        slug = f'{base[:40 - len(suffix)]}{suffix}'
        n += 1
    return slug


# Each entry is a set of literal Tailwind class fragments (never built by
# string-concatenating a color name at runtime) so the CDN JIT build - which
# scans the final rendered HTML, not the template source - reliably picks
# every one of them up. Keyed by FarmSite.Theme value.
THEME_PALETTES = {
    'emerald': {
        'gradient': 'from-emerald-950 via-emerald-900 to-emerald-800',
        'cta': 'bg-amber-500 hover:bg-amber-400 text-emerald-950',
        'accent_text': 'text-emerald-700 dark:text-emerald-400',
        'nav_hover': 'hover:text-emerald-700 dark:hover:text-emerald-400',
        'accent_bg': 'bg-emerald-700 hover:bg-emerald-800 dark:bg-emerald-600 dark:hover:bg-emerald-500',
        'badge_bg': 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-400',
        'mark_bg': 'bg-emerald-700 dark:bg-emerald-600',
    },
    'harvest': {
        'gradient': 'from-amber-950 via-amber-900 to-orange-800',
        'cta': 'bg-emerald-500 hover:bg-emerald-400 text-emerald-950',
        'accent_text': 'text-amber-700 dark:text-amber-400',
        'nav_hover': 'hover:text-amber-700 dark:hover:text-amber-400',
        'accent_bg': 'bg-amber-600 hover:bg-amber-700 dark:bg-amber-500 dark:hover:bg-amber-400',
        'badge_bg': 'bg-amber-50 text-amber-700 dark:bg-amber-950 dark:text-amber-400',
        'mark_bg': 'bg-amber-600 dark:bg-amber-500',
    },
    'sky': {
        'gradient': 'from-sky-950 via-sky-900 to-blue-800',
        'cta': 'bg-amber-400 hover:bg-amber-300 text-sky-950',
        'accent_text': 'text-sky-700 dark:text-sky-400',
        'nav_hover': 'hover:text-sky-700 dark:hover:text-sky-400',
        'accent_bg': 'bg-sky-700 hover:bg-sky-800 dark:bg-sky-600 dark:hover:bg-sky-500',
        'badge_bg': 'bg-sky-50 text-sky-700 dark:bg-sky-950 dark:text-sky-400',
        'mark_bg': 'bg-sky-700 dark:bg-sky-600',
    },
    'berry': {
        'gradient': 'from-rose-950 via-rose-900 to-red-900',
        'cta': 'bg-amber-400 hover:bg-amber-300 text-rose-950',
        'accent_text': 'text-rose-700 dark:text-rose-400',
        'nav_hover': 'hover:text-rose-700 dark:hover:text-rose-400',
        'accent_bg': 'bg-rose-700 hover:bg-rose-800 dark:bg-rose-600 dark:hover:bg-rose-500',
        'badge_bg': 'bg-rose-50 text-rose-700 dark:bg-rose-950 dark:text-rose-400',
        'mark_bg': 'bg-rose-700 dark:bg-rose-600',
    },
    'earth': {
        'gradient': 'from-stone-900 via-orange-950 to-stone-800',
        'cta': 'bg-amber-400 hover:bg-amber-300 text-stone-950',
        'accent_text': 'text-orange-800 dark:text-orange-400',
        'nav_hover': 'hover:text-orange-800 dark:hover:text-orange-400',
        'accent_bg': 'bg-orange-800 hover:bg-orange-900 dark:bg-orange-700 dark:hover:bg-orange-600',
        'badge_bg': 'bg-orange-50 text-orange-800 dark:bg-orange-950 dark:text-orange-400',
        'mark_bg': 'bg-orange-800 dark:bg-orange-700',
    },
}


class FarmSite(models.Model):
    """A farm's own publishable public website - one per farm. Nothing here
    is visible on the internet until is_published is set, so a farm can
    build the whole thing out privately first (see website.views.public_*,
    which 404 on an unpublished site regardless of whether any page
    exists)."""

    class Theme(models.TextChoices):
        EMERALD = 'emerald', _('Emerald')
        HARVEST = 'harvest', _('Harvest (amber)')
        SKY = 'sky', _('Sky (blue)')
        BERRY = 'berry', _('Berry (rose)')
        EARTH = 'earth', _('Earth (terracotta)')

    farm = models.OneToOneField('farms.Farm', on_delete=models.CASCADE, related_name='website')
    slug = models.SlugField(max_length=40, unique=True)
    tagline = models.CharField(max_length=150, blank=True)
    theme = models.CharField(max_length=20, choices=Theme.choices, default=Theme.EMERALD)
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = generate_site_slug(self.farm.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.farm.name} website ({self.slug})'

    @property
    def theme_palette(self):
        return THEME_PALETTES[self.theme]

    @classmethod
    def theme_swatches(cls):
        """(value, label, gradient classes) for every theme option - lets the
        settings form show an actual color swatch per choice, not just a
        text label, so picking one is a visual decision, not a guess."""
        return [(value, label, THEME_PALETTES[value]['gradient']) for value, label in cls.Theme.choices]


class SitePage(models.Model):
    """One page of a farm's site. `template` picks which layout renders it -
    this is a fixed-field, fixed-layout-choice page builder (pick a layout,
    fill in its fields) rather than a general drag-and-drop block editor,
    which is a deliberately smaller and more reliable thing to ship than a
    generic block system. A page with a blank slug is the site's homepage;
    the (site, slug) uniqueness constraint means at most one page can ever
    hold that blank slug per site."""

    class Template(models.TextChoices):
        HERO = 'hero', _('Hero landing')
        ARTICLE = 'article', _('Article / About')
        VERIFIED_STATS = 'verified_stats', _('Verified farm stats')
        PRODUCTS = 'products', _('Produce for sale')
        CONTACT = 'contact', _('Contact')

    site = models.ForeignKey(FarmSite, on_delete=models.CASCADE, related_name='pages')
    title = models.CharField(max_length=100)
    slug = models.SlugField(max_length=60, blank=True, help_text=_('Leave blank to make this the homepage.'))
    template = models.CharField(max_length=20, choices=Template.choices, default=Template.ARTICLE)

    headline = models.CharField(max_length=150, blank=True)
    subheading = models.CharField(max_length=255, blank=True)
    body = models.TextField(blank=True)
    # An uploaded file, stored on S3 in production (see settings.py's Media
    # storage block) - falls back to local disk with no AWS credentials
    # configured, which is fine for local dev but won't survive a Vercel
    # redeploy, so production needs real bucket credentials for uploads to
    # last. image_url stays as a lighter-weight alternative for a farm that
    # already has an image hosted elsewhere and doesn't want to upload one.
    image = models.ImageField(upload_to='website_pages/', blank=True)
    image_url = models.URLField(blank=True, help_text=_('Or link to an image already hosted elsewhere.'))
    cta_label = models.CharField(max_length=40, blank=True)
    cta_url = models.URLField(blank=True)
    contact_phone = models.CharField(max_length=20, blank=True)
    contact_email = models.EmailField(blank=True)

    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('site', 'slug')
        ordering = ['order', 'id']

    def __str__(self):
        return f'{self.site.farm.name} - {self.title}'

    @property
    def is_homepage(self):
        return self.slug == ''

    @property
    def display_image_url(self):
        """The uploaded file wins over the external link when both are set,
        since it's the one guaranteed to actually be this page's own image."""
        if self.image:
            return self.image.url
        return self.image_url


class Product(models.Model):
    """A produce listing on a farm's public site (see the PRODUCTS site page
    template) - order capture only, no payment gateway - a buyer submits an
    Order and the farmer arranges payment/delivery outside the app.
    Optionally tied to a real InventoryItem so price/name stay linked to
    actual farm stock rather than being a duplicate, freestanding listing."""

    farm = models.ForeignKey('farms.Farm', on_delete=models.CASCADE, related_name='products')
    inventory_item = models.ForeignKey(
        'inventory.InventoryItem', null=True, blank=True, on_delete=models.SET_NULL, related_name='+',
        help_text=_('Optional - link to the matching produce inventory item.')
    )
    name = models.CharField(max_length=100)
    description = models.CharField(max_length=255, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    unit = models.CharField(max_length=30, default='each', help_text=_('e.g. "per liter", "per kg", "per dozen"'))
    image = models.ImageField(upload_to='website_products/', blank=True)
    is_available = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f'{self.name} - {self.farm.name}'


class Order(models.Model):
    """A buyer's enquiry/order submitted from a farm's public site - capture
    only, no payment processed here. The farmer sees it in-app (see
    website.views.order_list) and advances its status by hand once they've
    actually arranged payment/delivery with the buyer."""

    class Status(models.TextChoices):
        NEW = 'new', _('New')
        CONTACTED = 'contacted', _('Contacted')
        FULFILLED = 'fulfilled', _('Fulfilled')
        CANCELLED = 'cancelled', _('Cancelled')

    farm = models.ForeignKey('farms.Farm', on_delete=models.CASCADE, related_name='orders')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='orders')
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    buyer_name = models.CharField(max_length=100)
    buyer_phone = models.CharField(max_length=20)
    buyer_note = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.NEW)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.buyer_name} - {self.quantity} {self.product.unit} {self.product.name}'
