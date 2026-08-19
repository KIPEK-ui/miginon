"""Predicts the next few days of milk yield per cow, and rolls those up
into block/farm totals. Falls back from a per-cow model to a farm-pooled
model when the individual cow doesn't have enough history yet (see
train.MIN_ROWS) - most cows will hit that fallback long before they
individually have 30 days of history, so this is what makes predictions
useful early rather than only after months of data per cow."""

from datetime import timedelta

from django.utils import timezone

from .explain import explain_prediction, plain_language_summary
from .features import DEFAULT_DAYS_IN_MILK, FEATURE_NAMES, build_training_rows
from .train import train_farm_model


def _latest_raw_features(farm, cow):
    """The feature snapshot to forecast forward from. Uses this cow's own
    most recent day if she has any history; otherwise (a brand-new cow with
    zero records of her own) falls back to farm-wide recent averages, so
    the farm-pooled model fallback in predict_cow can actually be used
    instead of silently producing nothing."""
    own_rows = build_training_rows(farm, cow=cow)
    if own_rows:
        return dict(own_rows[-1]['raw'])

    farm_rows = build_training_rows(farm)
    if not farm_rows:
        return None

    recent = farm_rows[-10:]
    averaged = {
        name: sum(r['raw'][name] for r in recent) / len(recent)
        for name in FEATURE_NAMES
    }
    if cow.last_calving_date:
        averaged['days_in_milk'] = (timezone.now().date() - cow.last_calving_date).days
    else:
        averaged['days_in_milk'] = DEFAULT_DAYS_IN_MILK
    return averaged


def predict_cow(farm, cow, days_ahead=3):
    """Returns a list of {date, predicted_liters, contributions,
    explanation} for the next `days_ahead` days, or None if there isn't
    enough farm-wide history yet to train anything at all."""
    trained = train_farm_model(farm, cow=cow)
    if trained is None:
        trained = train_farm_model(farm)
    if trained is None:
        return None

    latest_raw = _latest_raw_features(farm, cow)
    if latest_raw is None:
        return None

    today = timezone.now().date()
    predictions = []
    for i in range(1, days_ahead + 1):
        date = today + timedelta(days=i)
        raw = dict(latest_raw)
        raw['days_in_milk'] = raw['days_in_milk'] + i
        predicted, x_scaled = trained.predict_one(raw)
        contributions = explain_prediction(trained, x_scaled)
        predictions.append({
            'date': date,
            'predicted_liters': max(0.0, round(predicted, 1)),
            'contributions': contributions,
            'explanation': plain_language_summary(contributions),
        })
    return predictions


def predict_block(farm, block, cows, days_ahead=3):
    """Rolls up each cow's prediction into a block-level daily total.
    Returns None if none of the block's cows have a prediction available."""
    per_cow = {}
    for cow in cows:
        pred = predict_cow(farm, cow, days_ahead=days_ahead)
        if pred:
            per_cow[cow.id] = pred

    if not per_cow:
        return None

    today = timezone.now().date()
    rollup = []
    for i in range(days_ahead):
        date = today + timedelta(days=i + 1)
        total = sum(p[i]['predicted_liters'] for p in per_cow.values())
        rollup.append({'date': date, 'predicted_liters': round(total, 1)})
    return {'daily': rollup, 'per_cow': per_cow}


def predict_farm(farm, days_ahead=3):
    """Rolls up every block's prediction into a farm-level daily total."""
    from farms.models import Block

    blocks = Block.objects.filter(farm=farm)
    per_block = {}
    for block in blocks:
        cows = block.cows.filter(status='active')
        result = predict_block(farm, block, cows, days_ahead=days_ahead)
        if result:
            per_block[block.id] = result

    if not per_block:
        return None

    today = timezone.now().date()
    rollup = []
    for i in range(days_ahead):
        date = today + timedelta(days=i + 1)
        total = sum(r['daily'][i]['predicted_liters'] for r in per_block.values())
        rollup.append({'date': date, 'predicted_liters': round(total, 1)})
    return {'daily': rollup, 'per_block': per_block}
