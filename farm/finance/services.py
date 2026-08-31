from django.utils import timezone

from blockchain.services import anchor_hash, compute_content_hash


def anchor_transaction(transaction):
    """Anchors the transaction as originally recorded. Never called from an
    edit path - a later edit that no longer matches this hash is the audit
    trail correctly revealing a post-hoc change, not a defect to fix."""
    payload = {
        'farm_id': transaction.farm_id, 'kind': transaction.kind, 'category': transaction.category,
        'amount': str(transaction.amount), 'date': transaction.date.isoformat(), 'note': transaction.note,
    }
    content_hash = compute_content_hash(payload)
    result = anchor_hash('finance_topic_id', content_hash)
    if result:
        transaction.content_hash = content_hash
        transaction.hedera_topic_id = result['topic_id']
        transaction.hedera_sequence_number = result['sequence_number']
        transaction.hedera_consensus_timestamp = result['consensus_timestamp']
        transaction.hedera_anchored_at = timezone.now()
        transaction.save(update_fields=[
            'content_hash', 'hedera_topic_id', 'hedera_sequence_number',
            'hedera_consensus_timestamp', 'hedera_anchored_at',
        ])
