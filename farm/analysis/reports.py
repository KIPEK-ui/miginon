import calendar
from datetime import date

from django.db.models import Q, Sum
from django.utils import timezone

from cows.models import Cow, FeedingRecord, MilkRecord
from crops.models import CropActivity
from finance.models import Transaction
from inventory.models import InventoryItem, StockMovement


def _last_day_of_month(year, month):
    return date(year, month, calendar.monthrange(year, month)[1])


def _parse_iso_date(value, fallback):
    if not value:
        return fallback
    try:
        return date.fromisoformat(value)
    except ValueError:
        return fallback


def _parse_year_month(value, fallback):
    if value:
        try:
            year, month = value.split('-')
            return int(year), int(month)
        except (ValueError, IndexError):
            pass
    return fallback.year, fallback.month


def resolve_period(period_type, params):
    """Turn a period_type + query params into (start_date, end_date, label)."""
    today = timezone.now().date()

    if period_type == 'daily':
        d = _parse_iso_date(params.get('date'), today)
        return d, d, d.strftime('%d %b %Y')

    if period_type == 'quarterly':
        year = int(params.get('year') or today.year)
        quarter = int(params.get('quarter') or ((today.month - 1) // 3 + 1))
        quarter = min(max(quarter, 1), 4)
        start_month = (quarter - 1) * 3 + 1
        start = date(year, start_month, 1)
        end = _last_day_of_month(year, start_month + 2)
        return start, end, f'Q{quarter} {year}'

    if period_type == 'yearly':
        year = int(params.get('year') or today.year)
        return date(year, 1, 1), date(year, 12, 31), str(year)

    # default / 'monthly'
    year, month = _parse_year_month(params.get('month'), today)
    start = date(year, month, 1)
    end = _last_day_of_month(year, month)
    return start, end, start.strftime('%B %Y')


def build_report(farm, start, end, period_label):
    """Aggregate every module's activity for [start, end] into one structure
    shared by the CSV/XLSX/PDF exporters, so all three formats always agree."""
    milk_qs = MilkRecord.objects.filter(farm=farm, date__gte=start, date__lte=end)
    milk_total = milk_qs.aggregate(t=Sum('liters'))['t'] or 0
    active_cows = farm.cows.filter(status=Cow.Status.ACTIVE).count()
    avg_per_cow = (milk_total / active_cows) if active_cows else 0

    milk_by_block = list(
        milk_qs.values('block__name').annotate(liters=Sum('liters')).order_by('-liters')
    )
    milk_by_cow = list(
        milk_qs.values('cow__tag_id', 'cow__name', 'cow__block__name')
        .annotate(liters=Sum('liters'))
        .order_by('-liters')
    )
    milk_daily = list(milk_qs.values('date').annotate(liters=Sum('liters')).order_by('date'))

    feed_qs = FeedingRecord.objects.filter(farm=farm, date__gte=start, date__lte=end)
    feed_totals = feed_qs.aggregate(meal=Sum('dairy_meal_kg'), silage=Sum('silage_hay_kg'))
    feed_by_block = list(
        feed_qs.values('block__name')
        .annotate(meal=Sum('dairy_meal_kg'), silage=Sum('silage_hay_kg'))
        .order_by('block__name')
    )
    feed_daily = list(
        feed_qs.values('date')
        .annotate(meal=Sum('dairy_meal_kg'), silage=Sum('silage_hay_kg'))
        .order_by('date')
    )

    new_cows = list(
        farm.cows.filter(created_at__date__gte=start, created_at__date__lte=end)
        .select_related('block')
        .order_by('tag_id')
    )
    transfers = list(
        farm.cow_transfers.filter(transferred_at__date__gte=start, transferred_at__date__lte=end)
        .select_related('cow', 'from_block', 'to_block')
        .order_by('transferred_at')
    )

    activities = list(
        CropActivity.objects.filter(farm=farm, date__gte=start, date__lte=end)
        .select_related('crop')
        .order_by('date')
    )
    harvested_total = sum((a.quantity_harvested_kg or 0) for a in activities)

    movements = list(
        StockMovement.objects.filter(farm=farm, date__gte=start, date__lte=end)
        .select_related('item')
        .order_by('date')
    )
    inventory_levels = list(InventoryItem.objects.filter(farm=farm).order_by('name'))

    tx_qs = Transaction.objects.filter(farm=farm, date__gte=start, date__lte=end)
    tx_totals = tx_qs.aggregate(
        income=Sum('amount', filter=Q(kind=Transaction.Kind.INCOME)),
        expense=Sum('amount', filter=Q(kind=Transaction.Kind.EXPENSE)),
    )
    income = tx_totals['income'] or 0
    expense = tx_totals['expense'] or 0

    kind_labels = dict(Transaction.Kind.choices)
    category_labels = dict(Transaction.Category.choices)
    tx_by_category = [
        {
            'kind': kind_labels.get(row['kind'], row['kind']),
            'category': category_labels.get(row['category'], row['category']),
            'amount': row['amount'],
        }
        for row in tx_qs.values('kind', 'category').annotate(amount=Sum('amount')).order_by('kind', '-amount')
    ]
    transactions = list(tx_qs.order_by('date'))

    return {
        'farm': farm,
        'period_label': period_label,
        'start_date': start,
        'end_date': end,
        'generated_at': timezone.now(),
        'milk': {
            'total_liters': milk_total,
            'avg_per_cow': avg_per_cow,
            'by_block': milk_by_block,
            'by_cow': milk_by_cow,
            'daily': milk_daily,
        },
        'feeding': {
            'total_dairy_meal_kg': feed_totals['meal'] or 0,
            'total_silage_hay_kg': feed_totals['silage'] or 0,
            'by_block': feed_by_block,
            'daily': feed_daily,
        },
        'herd': {
            'active_cows': active_cows,
            'new_cows': new_cows,
            'transfers': transfers,
        },
        'crops': {
            'activities': activities,
            'total_harvested_kg': harvested_total,
        },
        'inventory': {
            'movements': movements,
            'levels': inventory_levels,
        },
        'finance': {
            'total_income': income,
            'total_expense': expense,
            'net': income - expense,
            'by_category': tx_by_category,
            'transactions': transactions,
        },
    }
