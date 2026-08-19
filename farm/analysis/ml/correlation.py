"""Pearson correlation between daily feed (kg) and daily milk (L), computed
at cow / block / herd level over a selectable period. Lightweight - no
model training involved, just numpy's exact Pearson coefficient."""

from collections import defaultdict

import numpy as np

from cows.models import FeedingRecordCow, MilkRecord

MIN_DAYS = 3


def _daily_totals(farm, start, end, cow=None, block=None):
    milk_qs = MilkRecord.objects.filter(farm=farm, date__gte=start, date__lte=end)
    feed_qs = FeedingRecordCow.objects.filter(
        feeding_record__farm=farm, feeding_record__date__gte=start, feeding_record__date__lte=end,
    )
    if cow is not None:
        milk_qs = milk_qs.filter(cow=cow)
        feed_qs = feed_qs.filter(cow=cow)
    elif block is not None:
        milk_qs = milk_qs.filter(block=block)
        feed_qs = feed_qs.filter(cow__block=block)

    milk_by_date = defaultdict(float)
    for date, liters in milk_qs.values_list('date', 'liters'):
        milk_by_date[date] += float(liters)

    feed_by_date = defaultdict(float)
    for date, dairy, silage in feed_qs.values_list('feeding_record__date', 'dairy_meal_kg', 'silage_hay_kg'):
        feed_by_date[date] += float(dairy) + float(silage)

    dates = sorted(set(milk_by_date) & set(feed_by_date))
    feed_series = [feed_by_date[d] for d in dates]
    milk_series = [milk_by_date[d] for d in dates]
    return dates, feed_series, milk_series


def feed_milk_correlation(farm, start, end, cow=None, block=None):
    """Returns {correlation, days, series} or None if there's too little
    overlapping feed+milk history in the period to say anything meaningful."""
    dates, feed_series, milk_series = _daily_totals(farm, start, end, cow=cow, block=block)
    if len(dates) < MIN_DAYS:
        return None

    feed_arr = np.array(feed_series)
    milk_arr = np.array(milk_series)
    if feed_arr.std() == 0 or milk_arr.std() == 0:
        correlation = 0.0
    else:
        correlation = float(np.corrcoef(feed_arr, milk_arr)[0, 1])

    return {
        'correlation': round(correlation, 2),
        'days': len(dates),
        'series': [{'date': d, 'feed_kg': f, 'milk_l': m} for d, f, m in zip(dates, feed_series, milk_series)],
    }
