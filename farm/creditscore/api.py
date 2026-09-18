"""Read-only credit-score API for outside data partners (SACCOs, MFIs,
insurers) - the first concrete piece of the data/reputation-marketplace
model: FarmIQ never hands over credit risk, it licenses verified,
Hedera-anchored score data to whoever needs it to underwrite a farmer.

Auth is a per-partner API key (X-API-Key header), not a session - there is
no partner login yet, just a key issued when a partner is onboarded (see
DataPartner). A missing/invalid key and a farm that exists but hasn't
consented both return the same 404, so a partner probing farm IDs can't
tell "wrong key" from "farm never shared with you" from "farm doesn't
exist" - not distinguishing these prevents both key-guessing and farm-ID
enumeration.
"""
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET

from farms.models import Farm

from .models import CreditScoreSnapshot, DataPartner, DataShareConsent


def _authenticate_partner(request):
    api_key = request.headers.get('X-API-Key', '')
    if not api_key:
        return None
    return DataPartner.objects.filter(api_key=api_key, status=DataPartner.Status.APPROVED).first()


@csrf_exempt
@require_GET
def farm_score(request, farm_id):
    partner = _authenticate_partner(request)
    if not partner:
        return JsonResponse({'error': 'invalid or missing API key'}, status=401)

    has_consent = DataShareConsent.objects.filter(
        farm_id=farm_id, partner=partner, revoked_at__isnull=True
    ).exists()
    if not has_consent:
        # Same response whether the farm doesn't exist or just hasn't
        # consented to this partner - see module docstring.
        return JsonResponse({'error': 'not found'}, status=404)

    farm = Farm.objects.get(id=farm_id)
    snapshot = CreditScoreSnapshot.objects.filter(farm=farm).first()
    if not snapshot:
        return JsonResponse({'error': 'no score computed yet for this farm'}, status=404)

    return JsonResponse({
        'farm_id': farm.id,
        'farm_name': farm.name,
        'score': snapshot.score,
        'tier': snapshot.tier,
        'method': snapshot.method,
        'population_size': snapshot.population_size,
        'computed_at': snapshot.computed_at.isoformat(),
        'explanation': snapshot.explanation,
        'category_breakdown': snapshot.category_breakdown,
        # Lets the partner independently confirm this score hasn't been
        # altered since it was anchored: recompute the hash from the fields
        # above (see blockchain.services.compute_content_hash) and check it
        # against the Hedera Consensus Service message at this topic/
        # sequence number.
        'verification': {
            'content_hash': snapshot.content_hash,
            'hedera_topic_id': snapshot.hedera_topic_id,
            'hedera_sequence_number': snapshot.hedera_sequence_number,
            'hedera_consensus_timestamp': snapshot.hedera_consensus_timestamp,
        },
    })
