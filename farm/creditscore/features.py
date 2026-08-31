"""Builds credit-scoring feature rows from a farm's own operational data -
finance, milk, crops, tasks, and FIQ ledger history. Every raw feature is
normalized/oriented so higher always means healthier, before any ML step
(see creditscore.scoring). None means "not applicable to this farm" (e.g.
a crop-only farm has no milk data) - it's imputed with the population
median in build_population_matrix, not penalized as zero here."""

from datetime import timedelta

import numpy as np
from django.db.models import Q, Sum
from django.utils import timezone

from blockchain.models import FiqLedgerEntry
from crops.models import CropActivity
from cows.models import Cow, MilkRecord
from farms.models import Farm
from finance.models import Transaction
from tasks.models import Task

MIN_FARM_AGE_DAYS = 30
MIN_ANY_RECORDS = 5

FEATURE_NAMES = [
    'farm_age_norm', 'expense_ratio_health', 'income_stability',
    'yield_consistency', 'herd_size_norm',
    'income_category_diversity', 'crop_activity_diversity',
    'task_on_time_rate', 'fiq_balance_norm', 'fiq_source_diversity',
]

WINDOW_DAYS = 90
INCOME_STABILITY_WINDOW_DAYS = 180
MAX_FARM_AGE_DAYS = 1095
MAX_HERD_SIZE = 50
MAX_FIQ_BALANCE = 500
# CropActivity.ActivityType has 6 choices including OTHER - diversity is
# measured over the 5 meaningful activity types, matching income_category_
# diversity's exclusion of Transaction.Category.OTHER below.
CROP_ACTIVITY_TYPES = 5
TRANSACTION_CATEGORIES = 9


def eligible_farms(as_of=None):
    """Farms old enough and active enough to be meaningfully scored - see
    MIN_FARM_AGE_DAYS/MIN_ANY_RECORDS. A brand-new or empty farm would just
    add noise to the peer population and can't be scored fairly anyway."""
    as_of = as_of or timezone.now().date()
    cutoff = as_of - timedelta(days=MIN_FARM_AGE_DAYS)
    farms = Farm.objects.filter(created_at__date__lte=cutoff)
    eligible_ids = []
    for farm in farms:
        record_count = (
            MilkRecord.objects.filter(farm=farm).count()
            + Transaction.objects.filter(farm=farm).count()
            + CropActivity.objects.filter(farm=farm).count()
            + Task.objects.filter(farm=farm, status=Task.Status.DONE).count()
        )
        if record_count >= MIN_ANY_RECORDS:
            eligible_ids.append(farm.id)
    return Farm.objects.filter(id__in=eligible_ids)


def _coefficient_of_variation(values):
    values = np.array(values, dtype=float)
    mean = values.mean()
    if mean <= 0:
        return None
    return float(values.std() / mean)


def _farm_age_norm(farm, as_of):
    age_days = (as_of - farm.created_at.date()).days
    return min(max(age_days, 0), MAX_FARM_AGE_DAYS) / MAX_FARM_AGE_DAYS


def _financial_features(farm, as_of):
    window_start = as_of - timedelta(days=WINDOW_DAYS)
    totals = Transaction.objects.filter(farm=farm, date__gte=window_start, date__lte=as_of).aggregate(
        income=Sum('amount', filter=Q(kind=Transaction.Kind.INCOME)),
        expense=Sum('amount', filter=Q(kind=Transaction.Kind.EXPENSE)),
    )
    income = float(totals['income'] or 0)
    expense = float(totals['expense'] or 0)
    if income <= 0:
        expense_ratio_health = 0.0 if expense > 0 else 0.5
    else:
        expense_ratio_health = 1 - min(max(expense / income, 0), 1)

    stability_start = as_of - timedelta(days=INCOME_STABILITY_WINDOW_DAYS)
    monthly = {}
    for date, amount in Transaction.objects.filter(
        farm=farm, kind=Transaction.Kind.INCOME, date__gte=stability_start, date__lte=as_of
    ).values_list('date', 'amount'):
        key = (date.year, date.month)
        monthly[key] = monthly.get(key, 0.0) + float(amount)
    if len(monthly) < 2:
        income_stability = None
    else:
        cv = _coefficient_of_variation(list(monthly.values()))
        income_stability = None if cv is None else 1 - min(max(cv, 0), 1)

    return expense_ratio_health, income_stability


def _production_features(farm, as_of):
    if not Cow.objects.filter(farm=farm, status=Cow.Status.ACTIVE).exists():
        return None, None

    herd_size_norm = min(farm.cow_count, MAX_HERD_SIZE) / MAX_HERD_SIZE

    window_start = as_of - timedelta(days=WINDOW_DAYS)
    daily_totals = {}
    for date, liters in MilkRecord.objects.filter(farm=farm, date__gte=window_start, date__lte=as_of).values_list('date', 'liters'):
        daily_totals[date] = daily_totals.get(date, 0.0) + float(liters)
    if len(daily_totals) < MIN_ANY_RECORDS:
        yield_consistency = None
    else:
        cv = _coefficient_of_variation(list(daily_totals.values()))
        yield_consistency = None if cv is None else 1 - min(max(cv, 0), 1)

    return yield_consistency, herd_size_norm


def _diversification_features(farm):
    categories = set(
        Transaction.objects.filter(farm=farm)
        .exclude(category=Transaction.Category.OTHER)
        .values_list('category', flat=True).distinct()
    )
    income_category_diversity = min(len(categories), TRANSACTION_CATEGORIES) / TRANSACTION_CATEGORIES

    crop_types = set(
        CropActivity.objects.filter(farm=farm)
        .exclude(activity_type=CropActivity.ActivityType.OTHER)
        .values_list('activity_type', flat=True).distinct()
    )
    crop_activity_diversity = min(len(crop_types), CROP_ACTIVITY_TYPES) / CROP_ACTIVITY_TYPES

    return income_category_diversity, crop_activity_diversity


def _behavioral_features(farm, as_of):
    window_start = as_of - timedelta(days=WINDOW_DAYS)
    done_tasks = Task.objects.filter(
        farm=farm, status=Task.Status.DONE, due_date__isnull=False,
        due_date__gte=window_start, due_date__lte=as_of,
    )
    total = done_tasks.count()
    if total == 0:
        return 0.5
    on_time = sum(
        1 for t in done_tasks.values_list('due_date', 'completed_at')
        if t[1] is not None and t[1].date() <= t[0]
    )
    return on_time / total


def _blockchain_features(farm):
    entries = FiqLedgerEntry.objects.filter(farm=farm)
    balance = float(entries.aggregate(total=Sum('amount'))['total'] or 0)
    fiq_balance_norm = min(balance, MAX_FIQ_BALANCE) / MAX_FIQ_BALANCE
    reasons = set(entries.values_list('reason', flat=True).distinct())
    fiq_source_diversity = min(len(reasons), 3) / 3
    return fiq_balance_norm, fiq_source_diversity


def build_farm_raw_features(farm, as_of=None):
    as_of = as_of or timezone.now().date()

    expense_ratio_health, income_stability = _financial_features(farm, as_of)
    yield_consistency, herd_size_norm = _production_features(farm, as_of)
    income_category_diversity, crop_activity_diversity = _diversification_features(farm)
    fiq_balance_norm, fiq_source_diversity = _blockchain_features(farm)

    return {
        'farm_age_norm': _farm_age_norm(farm, as_of),
        'expense_ratio_health': expense_ratio_health,
        'income_stability': income_stability,
        'yield_consistency': yield_consistency,
        'herd_size_norm': herd_size_norm,
        'income_category_diversity': income_category_diversity,
        'crop_activity_diversity': crop_activity_diversity,
        'task_on_time_rate': _behavioral_features(farm, as_of),
        'fiq_balance_norm': fiq_balance_norm,
        'fiq_source_diversity': fiq_source_diversity,
    }


def build_population_matrix(as_of=None):
    """Returns (farms, matrix, feature_names) - matrix is farms x features,
    with each column's None values replaced by that column's median across
    the population it was actually observed in (matching the median-
    imputation convention in analysis.ml.features), not a blanket zero."""
    as_of = as_of or timezone.now().date()
    farms = list(eligible_farms(as_of))
    raw_rows = [build_farm_raw_features(farm, as_of) for farm in farms]

    matrix = np.full((len(farms), len(FEATURE_NAMES)), np.nan)
    for i, row in enumerate(raw_rows):
        for j, name in enumerate(FEATURE_NAMES):
            value = row[name]
            if value is not None:
                matrix[i, j] = value

    for j in range(len(FEATURE_NAMES)):
        column = matrix[:, j]
        known = column[~np.isnan(column)]
        median = float(np.median(known)) if known.size else 0.5
        column[np.isnan(column)] = median

    return farms, matrix, FEATURE_NAMES
