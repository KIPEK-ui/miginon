from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _

from farms.permissions import any_member_required, manage_records_required

from .models import CreditScoreSnapshot, DataPartner, DataShareConsent
from .services import recompute_farm_score


def _contributions_display(contributions):
    """The stored contributions are exact but on a method-dependent raw
    scale (PCA loadings x standardized values for a population score;
    deviation-from-0.5 for a provisional one) - not comparable across
    snapshots and not meaningful as a literal points value to a farmer.
    Normalizes each snapshot's own contributions to a +/-100 "relative
    impact" scale, driven by its own largest contribution, purely for the
    bar chart - the underlying exact numbers stay in contributions/
    feature_values for anyone who wants them (e.g. via the anchored hash)."""
    if not contributions:
        return []
    max_abs = max(abs(c['contribution']) for c in contributions) or 1
    return [
        {'label': c['label'], 'impact': round(c['contribution'] / max_abs * 100)}
        for c in contributions
    ]


@any_member_required
def overview(request):
    farm = request.farm
    latest = CreditScoreSnapshot.objects.filter(farm=farm).first()
    history = CreditScoreSnapshot.objects.filter(farm=farm)[:10]
    return render(request, 'creditscore/overview.html', {
        'latest': latest,
        'history': history,
        'contributions_display': _contributions_display(latest.contributions) if latest else [],
    })


@manage_records_required
def recompute(request):
    if request.method != 'POST':
        return redirect('creditscore:overview')

    farm = request.farm
    before = CreditScoreSnapshot.objects.filter(farm=farm).first()
    snapshot = recompute_farm_score(farm, user=request.user)
    if before and snapshot.id == before.id:
        messages.info(request, _('Nothing has changed since the last recompute.'))
    else:
        messages.success(
            request,
            _('Credit score recomputed: %(score)s (%(tier)s).') % {'score': snapshot.score, 'tier': snapshot.get_tier_display()}
        )
    return redirect('creditscore:overview')


# Gated at the same tier as recompute above (Farmer/Manager/Supervisor) -
# deciding to hand a lender read access to the farm's score is the same
# class of decision as deciding what the score itself should reflect, not
# something a Worker should be able to do.
@manage_records_required
def data_sharing(request):
    farm = request.farm
    partners = DataPartner.objects.filter(status=DataPartner.Status.APPROVED).order_by('name')
    consents = {c.partner_id: c for c in DataShareConsent.objects.filter(farm=farm)}
    # Merged here rather than in the template - Django templates can't
    # index a dict by a loop variable without a custom filter, and this is
    # simpler than adding one just for this.
    rows = [{'partner': p, 'consent': consents.get(p.id)} for p in partners]
    return render(request, 'creditscore/data_sharing.html', {'rows': rows})


@manage_records_required
def grant_consent(request, partner_id):
    if request.method != 'POST':
        return redirect('creditscore:data_sharing')

    partner = get_object_or_404(DataPartner, id=partner_id, status=DataPartner.Status.APPROVED)
    # get_or_create rather than always creating a new row: the unique
    # (farm, partner) constraint means re-sharing with a partner you'd
    # previously revoked has to reactivate that same row, not fail on a
    # duplicate - see DataShareConsent's docstring on keeping one row per
    # pair for the audit trail.
    consent, created = DataShareConsent.objects.get_or_create(
        farm=request.farm, partner=partner, defaults={'granted_by': request.user}
    )
    if not created and not consent.is_active:
        consent.revoked_at = None
        consent.granted_by = request.user
        consent.save(update_fields=['revoked_at', 'granted_by'])
    messages.success(request, _('Sharing enabled with %(partner)s.') % {'partner': partner.name})
    return redirect('creditscore:data_sharing')


@manage_records_required
def revoke_consent(request, partner_id):
    if request.method != 'POST':
        return redirect('creditscore:data_sharing')

    consent = get_object_or_404(
        DataShareConsent, farm=request.farm, partner_id=partner_id, revoked_at__isnull=True
    )
    consent.revoked_at = timezone.now()
    consent.save(update_fields=['revoked_at'])
    messages.info(request, _('Sharing stopped with %(partner)s.') % {'partner': consent.partner.name})
    return redirect('creditscore:data_sharing')
