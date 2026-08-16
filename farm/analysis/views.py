from datetime import timedelta

from django.db.models import Q, Sum
from django.shortcuts import render
from django.utils import timezone

from cows.models import Cow, FeedingRecord, MilkRecord
from farms.models import Block
from farms.permissions import analysis_required
from finance.models import Transaction
from inventory.models import InventoryItem


@analysis_required
def overview(request):
    farm = request.farm
    today = timezone.now().date()
    week_start = today - timedelta(days=6)
    month_start = today - timedelta(days=29)

    daily_totals = {
        row['date']: row['total'] or 0
        for row in MilkRecord.objects.filter(farm=farm, date__gte=week_start)
        .values('date').annotate(total=Sum('liters'))
    }
    milk_trend = []
    for i in range(7):
        d = week_start + timedelta(days=i)
        milk_trend.append({'date': d, 'total': daily_totals.get(d, 0)})
    max_milk = max((row['total'] for row in milk_trend), default=0) or 1

    milk_week_total = sum(row['total'] for row in milk_trend)
    milk_month_total = (
        MilkRecord.objects.filter(farm=farm, date__gte=month_start).aggregate(t=Sum('liters'))['t'] or 0
    )
    active_cow_count = farm.cows.filter(status=Cow.Status.ACTIVE).count()
    avg_per_cow_week = (milk_week_total / active_cow_count) if active_cow_count else 0

    top_cows = (
        Cow.objects.filter(farm=farm, milk_records__date__gte=month_start)
        .annotate(total_liters=Sum('milk_records__liters'))
        .filter(total_liters__gt=0)
        .order_by('-total_liters')[:5]
    )

    block_totals = (
        Block.objects.filter(farm=farm)
        .annotate(week_liters=Sum('milk_records__liters', filter=Q(milk_records__date__gte=week_start)))
        .order_by('-week_liters')
    )

    feed_totals = FeedingRecord.objects.filter(farm=farm, date__gte=week_start).aggregate(
        meal=Sum('dairy_meal_kg'), silage=Sum('silage_hay_kg')
    )

    low_stock_items = [item for item in InventoryItem.objects.filter(farm=farm) if item.is_low_stock]

    finance_totals = Transaction.objects.filter(farm=farm, date__gte=month_start).aggregate(
        income=Sum('amount', filter=Q(kind=Transaction.Kind.INCOME)),
        expense=Sum('amount', filter=Q(kind=Transaction.Kind.EXPENSE)),
    )
    income = finance_totals['income'] or 0
    expense = finance_totals['expense'] or 0

    context = {
        'milk_trend': milk_trend,
        'max_milk': max_milk,
        'milk_week_total': milk_week_total,
        'milk_month_total': milk_month_total,
        'avg_per_cow_week': avg_per_cow_week,
        'active_cow_count': active_cow_count,
        'top_cows': top_cows,
        'block_totals': block_totals,
        'feed_meal_week': feed_totals['meal'] or 0,
        'feed_silage_week': feed_totals['silage'] or 0,
        'low_stock_items': low_stock_items,
        'income': income,
        'expense': expense,
        'net': income - expense,
    }
    return render(request, 'analysis/overview.html', context)
