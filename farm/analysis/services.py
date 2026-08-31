from django.utils import timezone

from blockchain.services import anchor_hash, compute_content_hash


def compute_prediction_hash(obj):
    """Hash the already-saved DB values (not the raw ML-output dict) -
    obj.contributions is guaranteed plain-JSON-safe once it's round-tripped
    through the JSONField, sidestepping numpy-scalar serialization issues
    in the raw ML output."""
    payload = {
        'farm_id': obj.farm_id, 'scope': obj.scope, 'cow_id': obj.cow_id, 'block_id': obj.block_id,
        'predicted_date': obj.predicted_date.isoformat(),
        'predicted_liters': str(obj.predicted_liters),  # Decimal isn't JSON-serializable directly
        'contributions': obj.contributions, 'explanation': obj.explanation,
    }
    return compute_content_hash(payload)


def anchor_changed_predictions(predictions):
    """_store_predictions runs on every page view of the predictions
    dashboards (not a scheduled job) - anchor only rows whose content
    actually changed since their last anchor, or every GET would submit a
    paid HCS message. Best-effort: a Hedera failure never blocks the
    predictions page from rendering."""
    for obj in predictions:
        new_hash = compute_prediction_hash(obj)
        if new_hash == obj.content_hash:
            continue
        result = anchor_hash('prediction_topic_id', new_hash)
        if result:
            obj.content_hash = new_hash
            obj.hedera_topic_id = result['topic_id']
            obj.hedera_sequence_number = result['sequence_number']
            obj.hedera_consensus_timestamp = result['consensus_timestamp']
            obj.hedera_anchored_at = timezone.now()
            obj.save(update_fields=[
                'content_hash', 'hedera_topic_id', 'hedera_sequence_number',
                'hedera_consensus_timestamp', 'hedera_anchored_at',
            ])
