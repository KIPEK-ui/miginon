from django.utils import timezone

from blockchain.services import anchor_hash, compute_content_hash

from .models import CreditScoreSnapshot
from .scoring import compute_population_scores, compute_provisional_score


def recompute_farm_score(farm, user=None):
    """Builds the population (or falls back to provisional if this farm
    isn't eligible for peer comparison yet), hash-diffs the new content
    against the farm's latest existing snapshot, and only creates + anchors
    a new row if the hash actually changed - a farmer clicking Recompute
    with nothing having actually changed shouldn't spam a paid HCS message.
    Returns the current snapshot (the existing, unchanged one if the hash
    matched)."""
    scores = compute_population_scores()
    result = scores.get(farm.id) or compute_provisional_score(farm)

    payload = {
        'farm_id': farm.id, 'score': result['score'], 'tier': result['tier'],
        'category_breakdown': result['category_breakdown'], 'feature_values': result['feature_values'],
        'contributions': result['contributions'], 'explanation': result['explanation'],
    }
    content_hash = compute_content_hash(payload)

    latest = CreditScoreSnapshot.objects.filter(farm=farm).first()
    if latest and latest.content_hash == content_hash:
        return latest

    snapshot = CreditScoreSnapshot.objects.create(
        farm=farm, score=result['score'], tier=result['tier'], method=result['method'],
        population_size=result['population_size'], category_breakdown=result['category_breakdown'],
        feature_values=result['feature_values'], contributions=result['contributions'],
        explanation=result['explanation'], content_hash=content_hash, computed_by=user,
    )
    anchor_result = anchor_hash('credit_score_topic_id', content_hash)
    if anchor_result:
        snapshot.hedera_topic_id = anchor_result['topic_id']
        snapshot.hedera_sequence_number = anchor_result['sequence_number']
        snapshot.hedera_consensus_timestamp = anchor_result['consensus_timestamp']
        snapshot.hedera_anchored_at = timezone.now()
        snapshot.save(update_fields=[
            'hedera_topic_id', 'hedera_sequence_number', 'hedera_consensus_timestamp', 'hedera_anchored_at',
        ])
    return snapshot
