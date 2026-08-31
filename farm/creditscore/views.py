from django.contrib import messages
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _

from farms.permissions import any_member_required, manage_records_required

from .models import CreditScoreSnapshot
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
