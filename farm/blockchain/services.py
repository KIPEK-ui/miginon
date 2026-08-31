import hashlib
import json
import logging
from decimal import Decimal

from django.conf import settings
from django.db import transaction

from hiero_sdk_python import (
    AccountId,
    Client,
    Network,
    PrivateKey,
    SupplyType,
    TokenCreateTransaction,
    TokenId,
    TokenMintTransaction,
    TokenType,
    TopicCreateTransaction,
    TopicId,
    TopicMessageSubmitTransaction,
)
from hiero_sdk_python.tokens.token_create_transaction import TokenKeys, TokenParams

from .models import HederaConfig

logger = logging.getLogger(__name__)

# Reward-amount constants for FIQ, the platform's single fungible token -
# kept together here so tuning them later doesn't mean hunting through
# cows/crops/blockchain views. Custody of every mint stays in the admin
# account (see get_client) - a farm's FIQ balance lives in
# blockchain.models.FiqLedgerEntry, not on-chain.
FIQ_REWARD_PER_COW = Decimal('10.00')
FIQ_REWARD_PER_KG_HARVESTED = Decimal('0.50')
FIQ_REWARD_PER_LITER = Decimal('1.00')
FIQ_REWARD_PER_TASK = Decimal('2.00')
FIQ_REWARD_PER_DATA_RECORD = Decimal('0.20')

_client = None


def _parse_operator_key(raw_key):
    """Hedera testnet accounts created with an EVM address use an ECDSA
    (secp256k1) key, not the platform-default Ed25519 - and PrivateKey's
    generic from_string() auto-detection can misidentify a raw 32-byte
    ECDSA key as Ed25519, producing a key that parses fine but signs
    incorrectly (Hedera rejects the resulting transaction with
    INVALID_SIGNATURE rather than a parse error, which makes this failure
    mode easy to misread as a credentials/network problem). Try ECDSA
    first (the more likely case for a key paired with an EVM address),
    then fall back to Ed25519, then the generic auto-detector."""
    key = raw_key.strip()
    if key.lower().startswith('0x'):
        key = key[2:]
    for parser in (PrivateKey.from_string_ecdsa, PrivateKey.from_string_ed25519, PrivateKey.from_string):
        try:
            return parser(key)
        except Exception:
            continue
    raise ValueError('Could not parse HEDERA_OPERATOR_KEY as either an ECDSA or Ed25519 key.')


def get_client():
    """Lazily build and cache the Hedera client from settings. Returns None
    if operator credentials aren't configured, exactly like every other
    best-effort external integration in this codebase (see
    weather.services.fetch_forecast) - callers must treat None as "Hedera
    unavailable" and continue without it."""
    global _client
    if _client is not None:
        return _client
    if not settings.HEDERA_OPERATOR_ID or not settings.HEDERA_OPERATOR_KEY:
        return None
    try:
        network = Network(settings.HEDERA_NETWORK)
        client = Client(network)
        client.set_operator(
            AccountId.from_string(settings.HEDERA_OPERATOR_ID),
            _parse_operator_key(settings.HEDERA_OPERATOR_KEY),
        )
    except Exception:
        logger.exception('Failed to build Hedera client')
        return None
    _client = client
    return _client


def _token_keys(client):
    return TokenKeys(admin_key=client.operator_private_key.public_key(), supply_key=client.operator_private_key.public_key())


def _create_nft_collection(client, name, symbol):
    receipt = TokenCreateTransaction(
        token_params=TokenParams(
            token_name=name, token_symbol=symbol, treasury_account_id=client.operator_account_id,
            token_type=TokenType.NON_FUNGIBLE_UNIQUE, supply_type=SupplyType.INFINITE,
        ),
        keys=_token_keys(client),
    ).execute(client)
    return str(receipt.token_id)


def _create_fiq_token(client):
    receipt = TokenCreateTransaction(
        token_params=TokenParams(
            token_name='FarmIQ', token_symbol='FIQ', treasury_account_id=client.operator_account_id,
            token_type=TokenType.FUNGIBLE_COMMON, decimals=2, initial_supply=0, supply_type=SupplyType.INFINITE,
        ),
        keys=_token_keys(client),
    ).execute(client)
    return str(receipt.token_id)


def _create_topic(client, memo):
    receipt = TopicCreateTransaction(memo=memo).execute(client)
    return str(receipt.topic_id)


# field_name -> creator function, used by _ensure_id below. Kept as a single
# table so "which Hedera object backs which HederaConfig field" lives in one
# place rather than being re-derived in every caller.
_CREATORS = {
    'cow_nft_token_id': lambda client: _create_nft_collection(client, 'FarmIQ Herd Registry', 'FIQCOW'),
    'harvest_nft_token_id': lambda client: _create_nft_collection(client, 'FarmIQ Harvest Certificates', 'FIQCROP'),
    'fiq_token_id': _create_fiq_token,
    'prediction_topic_id': lambda client: _create_topic(client, 'FarmIQ AI prediction anchors'),
    'finance_topic_id': lambda client: _create_topic(client, 'FarmIQ finance transaction anchors'),
    'credit_score_topic_id': lambda client: _create_topic(client, 'FarmIQ credit score anchors'),
}


def _ensure_id(client, field_name):
    """Return the platform's shared ID for `field_name` (a HederaConfig
    field), creating it on Hedera the first time it's needed. Locks the
    config row for the duration of a create so two concurrent requests
    can't each create a duplicate token/topic - after the first creation
    this is just a fast DB read for the lifetime of the deployment."""
    with transaction.atomic():
        config = HederaConfig.objects.select_for_update().get_or_create(pk=1)[0]
        existing = getattr(config, field_name)
        if existing:
            return existing
        new_id = _CREATORS[field_name](client)
        setattr(config, field_name, new_id)
        config.save(update_fields=[field_name, 'updated_at'])
        return new_id


def _nft_metadata(payload: dict) -> bytes:
    """Hedera NFT metadata is public and capped at 100 bytes - keep it to a
    tiny, non-sensitive JSON blob (never anything operationally sensitive)."""
    return json.dumps(payload, separators=(',', ':')).encode('utf-8')[:100]


def mint_cow_nft(cow):
    """Mint one serial on the shared herd-registry NFT collection for this
    cow (creating the collection itself on first-ever use). Returns
    {'token_id', 'serial_number', 'transaction_id'} or None. Never raises -
    a Hedera outage must never block a cow from being registered."""
    client = get_client()
    if client is None:
        return None
    try:
        token_id = _ensure_id(client, 'cow_nft_token_id')
        metadata = _nft_metadata({'tag_id': cow.tag_id, 'breed': cow.breed, 'farm': cow.farm.name})
        receipt = TokenMintTransaction(token_id=TokenId.from_string(token_id), metadata=[metadata]).execute(client)
        return {
            'token_id': token_id,
            'serial_number': receipt.serial_numbers[0],
            'transaction_id': str(receipt.transaction_id),
        }
    except Exception:
        logger.exception('Failed to mint cow NFT for cow %s', cow.id)
        return None


def mint_harvest_nft(activity):
    """Mint one serial on the shared harvest-certificate NFT collection for
    this harvest activity. Same contract as mint_cow_nft."""
    client = get_client()
    if client is None:
        return None
    try:
        token_id = _ensure_id(client, 'harvest_nft_token_id')
        metadata = _nft_metadata({
            'crop': activity.crop.name, 'kg': str(activity.quantity_harvested_kg),
            'date': activity.date.isoformat(), 'farm': activity.farm.name,
        })
        receipt = TokenMintTransaction(token_id=TokenId.from_string(token_id), metadata=[metadata]).execute(client)
        return {
            'token_id': token_id,
            'serial_number': receipt.serial_numbers[0],
            'transaction_id': str(receipt.transaction_id),
        }
    except Exception:
        logger.exception('Failed to mint harvest NFT for activity %s', activity.id)
        return None


def mint_fiq(amount: Decimal):
    """Mint `amount` FIQ (2 decimals) to the treasury/admin account,
    creating the FIQ token itself on first-ever use. A dumb HTS primitive -
    it doesn't know *why* FIQ is being minted; callers create the matching
    blockchain.models.FiqLedgerEntry themselves, only on success. Returns
    {'transaction_id', 'amount_minted'} or None."""
    client = get_client()
    if client is None:
        return None
    try:
        token_id = _ensure_id(client, 'fiq_token_id')
        smallest_unit = int((amount * 100).to_integral_value())
        receipt = TokenMintTransaction(token_id=TokenId.from_string(token_id), amount=smallest_unit).execute(client)
        return {'transaction_id': str(receipt.transaction_id), 'amount_minted': amount}
    except Exception:
        logger.exception('Failed to mint %s FIQ', amount)
        return None


def anchor_hash(config_field: str, content_hash: str):
    """Submit content_hash (and nothing else - HCS messages are public, so
    only hashes get published, never raw farm data) to the shared topic
    named by `config_field` ('prediction_topic_id' or 'finance_topic_id'),
    creating that topic on first-ever use. Returns {'topic_id',
    'sequence_number', 'consensus_timestamp'} or None. A dumb primitive -
    the caller decides what/when to hash."""
    client = get_client()
    if client is None:
        return None
    try:
        topic_id = _ensure_id(client, config_field)
        receipt = TopicMessageSubmitTransaction(topic_id=TopicId.from_string(topic_id), message=content_hash).execute(client)
        # The transaction's valid_start (not a separate TransactionRecordQuery
        # for the network's exact consensus timestamp - that would cost an
        # extra round-trip) is close enough to be a useful display/audit
        # timestamp and is enough to look the message up on HashScan.
        valid_start = receipt.transaction_id.valid_start if receipt.transaction_id else None
        consensus_timestamp = f'{valid_start.seconds}.{valid_start.nanos}' if valid_start else ''
        return {
            'topic_id': topic_id,
            'sequence_number': receipt.topic_sequence_number,
            'consensus_timestamp': consensus_timestamp,
        }
    except Exception:
        logger.exception('Failed to anchor hash on %s', config_field)
        return None


def compute_content_hash(payload: dict) -> str:
    """Canonical SHA-256 hash of a JSON-safe dict - shared by both the
    prediction-anchoring (analysis app) and finance-anchoring (finance app)
    use cases so the same hashing rule is used everywhere."""
    canonical = json.dumps(payload, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()
