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


class LearningPath(models.Model):
    slug = models.SlugField(unique=True)
    title = models.CharField(max_length=150)
    description = models.CharField(max_length=255)
    icon = models.CharField(max_length=50, default='school-outline')

    class Meta:
        ordering = ['title']

    def __str__(self):
        return self.title


class LearningLesson(models.Model):
    path = models.ForeignKey(LearningPath, on_delete=models.CASCADE, related_name='lessons')
    order = models.PositiveIntegerField()
    title = models.CharField(max_length=150)
    icon = models.CharField(max_length=50, default='book-outline')
    summary = models.CharField(max_length=255)
    content = models.TextField(
        help_text=_('One paragraph or bullet per line. A line starting with "## " renders as a subheading.')
    )
    key_terms = models.TextField(
        blank=True, help_text=_('One "Term: definition" per line - renders as a glossary block. Optional.')
    )
    search_terms = models.CharField(max_length=200, blank=True)

    class Meta:
        unique_together = ('path', 'order')
        ordering = ['path', 'order']

    def __str__(self):
        return f'{self.path.title} - {self.order}. {self.title}'

    def content_blocks(self):
        """Split into (is_heading, text) pairs so the template can render
        "## " lines as subheadings without a template-side string check."""
        blocks = []
        for line in self.content.splitlines():
            line = line.strip()
            if not line:
                continue
            if line.startswith('## '):
                blocks.append({'heading': True, 'text': line[3:].strip()})
            else:
                blocks.append({'heading': False, 'text': line})
        return blocks

    def key_terms_list(self):
        terms = []
        for line in self.key_terms.splitlines():
            line = line.strip()
            if not line:
                continue
            term, sep, definition = line.partition(':')
            terms.append({'term': term.strip(), 'definition': definition.strip() if sep else ''})
        return terms

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


class CropSuitability(models.Model):
    """Which crops suit a given county - static reference data seeded by
    migration (see advisory/migrations/0004_seed_crop_suitability.py), same
    pattern as AgriCenter/DiseaseCatalog above. Authored per agro-ecological
    zone (`zone`, kept for transparency) and expanded to one row per
    (county, crop_name) so a lookup by farms.Farm.county - the reliable
    signup-time location field, unlike lat/lon which isn't always geocoded -
    stays a simple filter (see advisory.services.recommended_crops_for_county)."""

    county = models.CharField(max_length=100, help_text=_('Matches a key in farms.kenya_data.COUNTY_TOWNS.'))
    zone = models.CharField(max_length=100, help_text=_('The agro-ecological zone this recommendation is based on.'))
    crop_name = models.CharField(max_length=100)
    notes = models.CharField(max_length=255, help_text=_('Why this crop suits the zone.'))
    planting_season = models.CharField(max_length=100, blank=True, help_text=_('e.g. "March-May long rains"'))

    class Meta:
        ordering = ['county', 'crop_name']
        verbose_name_plural = 'Crop suitability'

    def __str__(self):
        return f'{self.crop_name} - {self.county}'
