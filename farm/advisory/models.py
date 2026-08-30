from urllib.parse import quote_plus

from django.db import models
from django.utils.translation import gettext_lazy as _


def youtube_search_url(terms):
    if not terms:
        return None
    return f'https://www.youtube.com/results?search_query={quote_plus(terms)}'


class DiseaseCatalog(models.Model):
    class Category(models.TextChoices):
        DAIRY = 'dairy', _('Dairy cattle')
        CROP = 'crop', _('Crop')

    category = models.CharField(max_length=5, choices=Category.choices)
    name = models.CharField(max_length=150)
    affected = models.CharField(
        max_length=150,
        help_text=_('What it affects, e.g. "Dairy cattle" or a crop like "Maize", "Napier grass".')
    )
    icon = models.CharField(max_length=50, default='medkit-outline')
    symptoms = models.TextField()
    cause = models.TextField(blank=True)
    prevention = models.TextField()
    treatment = models.TextField()
    source_note = models.CharField(
        max_length=255, blank=True,
        help_text=_('Where this guidance is drawn from, e.g. "KALRO / Kenya Veterinary Board guidance".')
    )
    search_terms = models.CharField(
        max_length=200, blank=True,
        help_text=_('Search phrase used to suggest related videos, e.g. "East Coast Fever cattle treatment Kenya".')
    )

    class Meta:
        ordering = ['category', 'name']
        verbose_name_plural = 'Disease catalog'

    def __str__(self):
        return f'{self.name} ({self.affected})'

    def youtube_search_url(self):
        return youtube_search_url(self.search_terms)


class Guide(models.Model):
    class Category(models.TextChoices):
        SILAGE = 'silage', _('Silage preparation')
        VALUE_ADDITION = 'value_addition', _('Milk value addition')
        LAND_PREP = 'land_prep', _('Land preparation')
        SOIL_SAMPLING = 'soil_sampling', _('Soil sampling')
        PLANTING = 'planting', _('Crop planting')
        HARVESTING = 'harvesting', _('Harvesting')

    category = models.CharField(max_length=20, choices=Category.choices)
    title = models.CharField(max_length=150)
    icon = models.CharField(max_length=50, default='book-outline')
    summary = models.CharField(max_length=255)
    steps = models.TextField(help_text=_('One step per line.'))
    tips = models.TextField(blank=True, help_text=_('One tip per line - optional.'))
    source_note = models.CharField(max_length=255, blank=True)
    search_terms = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ['category', 'title']

    def __str__(self):
        return self.title

    def steps_list(self):
        return [s.strip() for s in self.steps.splitlines() if s.strip()]

    def tips_list(self):
        return [t.strip() for t in self.tips.splitlines() if t.strip()]

    def youtube_search_url(self):
        return youtube_search_url(self.search_terms)


class AgriCenter(models.Model):
    name = models.CharField(max_length=150)
    county = models.CharField(max_length=100)
    town = models.CharField(max_length=100, blank=True)
    latitude = models.DecimalField(max_digits=8, decimal_places=5)
    longitude = models.DecimalField(max_digits=8, decimal_places=5)
    coordinates_are_approximate = models.BooleanField(
        default=False,
        help_text=_('True if the coordinates are a town-level estimate rather than the exact facility location.')
    )
    focus_area = models.CharField(max_length=150, blank=True)
    phone = models.CharField(max_length=100, blank=True)
    email = models.CharField(max_length=100, blank=True)
    source_note = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ['county', 'name']

    def __str__(self):
        return f'{self.name} ({self.county})'
