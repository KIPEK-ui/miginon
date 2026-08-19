"""Builds feature rows for the milk-yield prediction model from a farm's
own historical records - one row per (cow, date) where a milk total
exists. Feature choices are deliberately modest, matching realistic
single-farm data volumes (dozens to low-thousands of rows, not big data)."""

from collections import defaultdict

from cows.models import Cow, FeedingRecordCow, MilkRecord

FEATURE_NAMES = ['days_in_milk', 'dairy_meal_kg', 'silage_hay_kg', 'rolling_avg_liters_7d', 'is_heifer']

DEFAULT_DAYS_IN_MILK = 150


def build_training_rows(farm, cow=None):
    """Returns a list of {cow_id, date, liters, raw: {feature: value}}
    dicts, ordered by cow then date - restricted to a single cow if given,
    else the whole farm."""
    milk_qs = MilkRecord.objects.filter(farm=farm)
    if cow is not None:
        milk_qs = milk_qs.filter(cow=cow)

    daily_milk = defaultdict(float)
    for cow_id, date, liters in milk_qs.values_list('cow_id', 'date', 'liters'):
        daily_milk[(cow_id, date)] += float(liters)

    feed_qs = FeedingRecordCow.objects.filter(feeding_record__farm=farm).select_related('feeding_record')
    if cow is not None:
        feed_qs = feed_qs.filter(cow=cow)

    daily_feed = defaultdict(lambda: {'dairy': 0.0, 'silage': 0.0})
    for allocation in feed_qs:
        key = (allocation.cow_id, allocation.feeding_record.date)
        daily_feed[key]['dairy'] += float(allocation.dairy_meal_kg)
        daily_feed[key]['silage'] += float(allocation.silage_hay_kg)

    cows_by_id = {c.id: c for c in Cow.objects.filter(farm=farm)}

    by_cow_dates = defaultdict(list)
    for cow_id, date in daily_milk:
        by_cow_dates[cow_id].append(date)
    for cow_id in by_cow_dates:
        by_cow_dates[cow_id].sort()

    rows = []
    for cow_id, dates in by_cow_dates.items():
        c = cows_by_id.get(cow_id)
        if c is None:
            continue
        history = []
        for date in dates:
            liters = daily_milk[(cow_id, date)]
            recent = [l for d, l in history if (date - d).days <= 7]
            rolling_avg = (sum(recent) / len(recent)) if recent else liters

            days_in_milk = (date - c.last_calving_date).days if c.last_calving_date else None
            feed = daily_feed.get((cow_id, date), {'dairy': 0.0, 'silage': 0.0})

            rows.append({
                'cow_id': cow_id,
                'date': date,
                'liters': liters,
                'raw': {
                    'days_in_milk': days_in_milk,
                    'dairy_meal_kg': feed['dairy'],
                    'silage_hay_kg': feed['silage'],
                    'rolling_avg_liters_7d': rolling_avg,
                    'is_heifer': 1.0 if c.category == Cow.Category.HEIFER else 0.0,
                },
            })
            history.append((date, liters))

    known_dim = [r['raw']['days_in_milk'] for r in rows if r['raw']['days_in_milk'] is not None]
    median_dim = sorted(known_dim)[len(known_dim) // 2] if known_dim else DEFAULT_DAYS_IN_MILK
    for r in rows:
        if r['raw']['days_in_milk'] is None:
            r['raw']['days_in_milk'] = median_dim

    return rows
