import secrets

from django.conf import settings
from django.db import models
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _


def generate_partner_slug(name):
    """Mirrors farms.models.generate_farm_code's approach: derive a slug
    from the name, then disambiguate with a numeric suffix on collision -
    self-serve applicants never type a slug themselves (see
    creditscore.forms.PartnerApplicationForm), so this has to never fail."""
    base = slugify(name)[:50] or 'partner'
    slug = base
    suffix = 1
    while DataPartner.objects.filter(slug=slug).exists():
        suffix += 1
        slug = f'{base}-{suffix}'
    return slug


class DataPartner(models.Model):
    """An outside organization (SACCO, MFI, insurer) authorized to look up
    credit scores through the read-only partner API, gated per-farm by
    DataShareConsent below. One row per partner organization, not per
    person at the partner - individual staff accounts at the partner are
    out of scope until a real integration actually asks for them.

    Partners can self-serve apply (creditscore.public.partner_apply) but
    start PENDING - an application alone never grants API access, since
    the API key it comes with would otherwise work immediately for any
    farm that happens to consent before a human ever reviewed who's asking.
    Staff move a partner to APPROVED (and email them their key) via the
    "Approve selected partners" admin action."""

    class Status(models.TextChoices):
        PENDING = 'pending', _('Pending review')
        APPROVED = 'approved', _('Approved')
        SUSPENDED = 'suspended', _('Suspended')

    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=60, unique=True)
    contact_name = models.CharField(max_length=150, blank=True)
    contact_email = models.EmailField(blank=True)
    api_key = models.CharField(max_length=64, unique=True, editable=False)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.api_key:
            self.api_key = secrets.token_hex(32)
        if not self.slug:
            self.slug = generate_partner_slug(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class DataShareConsent(models.Model):
    """A farm's explicit, revocable authorization for one partner to read
    its credit score. Required (Kenya's Data Protection Act 2019, and any
    lender's own compliance requirements) before a farm's financial data
    reaches a third party - the partner API checks this on every request,
    not just at integration setup, so revoking here takes effect
    immediately. Kept as a real row (revoked_at) rather than deleting on
    revoke, so there's an audit trail of what was ever shared and when."""

    farm = models.ForeignKey('farms.Farm', on_delete=models.CASCADE, related_name='data_share_consents')
    partner = models.ForeignKey(DataPartner, on_delete=models.CASCADE, related_name='consents')
    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='+'
    )
    granted_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['farm', 'partner'], name='unique_farm_partner_consent'),
        ]

    @property
    def is_active(self):
        return self.revoked_at is None

    def __str__(self):
        status = 'active' if self.is_active else 'revoked'
        return f'{self.farm} -> {self.partner} ({status})'


class CreditScoreSnapshot(models.Model):
    """Append-only, like a finance Transaction's anchor - never overwritten,
    so a lender-facing audit trail can show score evolution over time with
    each historical value provably unaltered. category_breakdown and
    feature_values hold ONLY this farm's own numbers, never another farm's
    or the population matrix itself - see creditscore.services."""

    class Tier(models.TextChoices):
        POOR = 'poor', _('Poor')
        FAIR = 'fair', _('Fair')
        GOOD = 'good', _('Good')
        EXCELLENT = 'excellent', _('Excellent')

    class Method(models.TextChoices):
        POPULATION = 'population', _('Population PCA/KMeans')
        PROVISIONAL = 'provisional', _('Provisional composite (limited peer data)')

    farm = models.ForeignKey('farms.Farm', on_delete=models.CASCADE, related_name='credit_score_snapshots')
    computed_at = models.DateTimeField(auto_now_add=True)
    score = models.PositiveSmallIntegerField()
    tier = models.CharField(max_length=10, choices=Tier.choices)
    method = models.CharField(max_length=12, choices=Method.choices)
    population_size = models.PositiveIntegerField()
    category_breakdown = models.JSONField(default=dict, blank=True)
    feature_values = models.JSONField(default=dict, blank=True)
    contributions = models.JSONField(
        default=list, blank=True,
        help_text=_('Exact per-feature drivers of the score - see creditscore.explain.')
    )
    explanation = models.CharField(max_length=255, blank=True)
    content_hash = models.CharField(max_length=64, blank=True)
    hedera_topic_id = models.CharField(max_length=20, blank=True)
    hedera_sequence_number = models.PositiveIntegerField(null=True, blank=True)
    hedera_consensus_timestamp = models.CharField(max_length=40, blank=True)
    hedera_anchored_at = models.DateTimeField(null=True, blank=True)
    computed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+'
    )

    class Meta:
        ordering = ['-computed_at']

    def __str__(self):
        return f'{self.farm.name} - {self.score} ({self.get_tier_display()})'
