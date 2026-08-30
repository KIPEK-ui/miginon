import logging
from datetime import timedelta

from django.contrib import messages
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _

from core.email import send_styled_email
from cows.models import Cow, FeedingRecord, MilkRecord
from farms.models import Block
from farms.permissions import analysis_required
from finance.models import Transaction
from inventory.models import InventoryItem

from weather.services import get_forecast_summary

from .exporters import build_pdf_bytes, export_csv, export_pdf, export_xlsx
from .ml.correlation import feed_milk_correlation
from .ml.predict import predict_block, predict_cow, predict_farm
from .models import MilkPrediction
from .reports import build_report, resolve_period

logger = logging.getLogger(__name__)


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
        'weather': get_forecast_summary(farm),
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
        'today': today,
        'current_month': today.strftime('%Y-%m'),
        'export_years': range(today.year, today.year - 6, -1),
    }
    return render(request, 'analysis/overview.html', context)


@analysis_required
def export(request):
    period_type = request.GET.get('period_type', 'monthly')
    export_format = request.GET.get('export_format', 'pdf')
    start, end, label = resolve_period(period_type, request.GET)
    report = build_report(request.farm, start, end, label)

    if export_format == 'csv':
        return export_csv(report)
    if export_format == 'xlsx':
        return export_xlsx(report)
    return export_pdf(report)


@analysis_required
def email_report(request):
    if request.method != 'POST':
        return redirect('analysis:overview')

    period_type = request.POST.get('period_type', 'monthly')
    start, end, label = resolve_period(period_type, request.POST)
    report = build_report(request.farm, start, end, label)
    pdf_bytes = build_pdf_bytes(report)

    try:
        send_styled_email(
            to=request.user.email,
            subject=_('%(farm)s - %(label)s report') % {'farm': request.farm.name, 'label': label},
            template_name='emails/farm_report.html',
            context={
                'report': report,
                'farm': request.farm,
                'analysis_url': request.build_absolute_uri(reverse('analysis:overview')),
            },
            attachments=[(f'{request.farm.code}-report.pdf', pdf_bytes, 'application/pdf')],
        )
        messages.success(request, _('Report emailed to %(email)s.') % {'email': request.user.email})
    except Exception:
        logger.exception('Failed to email farm report')
        messages.error(request, _('Could not send the report email. Please try again later.'))
    return redirect('analysis:overview')


# ------------------------------------------------------- AI production analytics

def _store_predictions(farm, scope, predictions, cow=None, block=None):
    for p in predictions:
        MilkPrediction.objects.update_or_create(
            farm=farm, scope=scope, cow=cow, block=block, predicted_date=p['date'],
            defaults={
                'predicted_liters': p['predicted_liters'],
                'contributions': p.get('contributions', []),
                'explanation': p.get('explanation', ''),
            },
        )


@analysis_required
def predictions_overview(request):
    farm = request.farm
    today = timezone.now().date()
    start = today - timedelta(days=29)

    farm_forecast = predict_farm(farm)
    if farm_forecast:
        _store_predictions(farm, MilkPrediction.Scope.FARM, farm_forecast['daily'])

    correlation = feed_milk_correlation(farm, start, today)
    blocks = Block.objects.filter(farm=farm).order_by('name')

    return render(request, 'analysis/predictions_overview.html', {
        'forecast': farm_forecast['daily'] if farm_forecast else None,
        'correlation': correlation,
        'blocks': blocks,
    })


@analysis_required
def predictions_block(request, block_id):
    # context key can't be "block" - Django's {% block %} tag reserves that
    # name in the template's own context (see farms.views.block_detail).
    farm = request.farm
    block_obj = get_object_or_404(Block, id=block_id, farm=farm)
    today = timezone.now().date()
    start = today - timedelta(days=29)

    cows = block_obj.cows.filter(status=Cow.Status.ACTIVE)
    result = predict_block(farm, block_obj, cows)
    if result:
        _store_predictions(farm, MilkPrediction.Scope.BLOCK, result['daily'], block=block_obj)

    correlation = feed_milk_correlation(farm, start, today, block=block_obj)

    return render(request, 'analysis/predictions_block.html', {
        'block_obj': block_obj,
        'forecast': result['daily'] if result else None,
        'correlation': correlation,
        'cows': cows,
    })


@analysis_required
def predictions_cow(request, cow_id):
    farm = request.farm
    cow = get_object_or_404(Cow, id=cow_id, farm=farm)
    today = timezone.now().date()
    start = today - timedelta(days=29)

    predictions = predict_cow(farm, cow)
    if predictions:
        _store_predictions(farm, MilkPrediction.Scope.COW, predictions, cow=cow)

    correlation = feed_milk_correlation(farm, start, today, cow=cow)

    return render(request, 'analysis/predictions_cow.html', {
        'cow': cow,
        'predictions': predictions,
        'correlation': correlation,
    })
