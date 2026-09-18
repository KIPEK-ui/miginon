from datetime import timedelta
from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone
from django.utils.translation import gettext as _

from crops.models import Crop
from cows.models import MilkRecord
from finance.models import Transaction
from inventory.models import InventoryItem
from tasks.models import Task

from .models import FarmInsight

# Mirrors analysis.ml.train.MIN_ROWS - below this, a farm hasn't got enough
# milk history for a trend to mean anything, so it gets a plain "getting
# started" tip instead. This is the literal "grows with the farm" behavior:
# a new farm sees simple tips, an established one sees real trend detection.
MIN_MILK_ROWS = 30
MILK_TREND_THRESHOLD = Decimal('0.10')
FINANCE_TREND_THRESHOLD = Decimal('0.30')


def _upsert(farm, seen_keys, key, category, severity, title, description):
    FarmInsight.objects.update_or_create(
        farm=farm, key=key,
        defaults={'category': category, 'severity': severity, 'title': title, 'description': description},
    )
    seen_keys.add(key)


def _cold_start_tip(farm, seen_keys):
    if MilkRecord.objects.filter(farm=farm).count() >= MIN_MILK_ROWS:
        return
    _upsert(
        farm, seen_keys, 'cold_start_milk', FarmInsight.Category.MILK, FarmInsight.Severity.INFO,
        _('Keep logging milk daily'),
        _("Once you've logged 30 days of milk records, you'll start seeing yield trend insights here."),
    )


def _milk_trend(farm, seen_keys):
    if MilkRecord.objects.filter(farm=farm).count() < MIN_MILK_ROWS:
        return
    today = timezone.localdate()

    def liters_between(start, end):
        return MilkRecord.objects.filter(farm=farm, date__gte=start, date__lt=end).aggregate(
            total=Sum('liters')
        )['total'] or Decimal('0')

    # Two clean, non-overlapping 7-day windows: [today-6, today] and
    # [today-13, today-7] - using today-7/today-14 as the boundaries here
    # would make "last 7 days" actually span 8 days (today-7 through today
    # inclusive) while "prior 7 days" only covers 7, skewing the comparison.
    last_7 = liters_between(today - timedelta(days=6), today + timedelta(days=1))
    prior_7 = liters_between(today - timedelta(days=13), today - timedelta(days=6))
    if prior_7 <= 0:
        return
    change = (last_7 - prior_7) / prior_7
    if change <= -MILK_TREND_THRESHOLD:
        _upsert(
            farm, seen_keys, 'milk_trend', FarmInsight.Category.MILK, FarmInsight.Severity.WARNING,
            _('Milk yield is down'),
            _('This week\'s milk production (%(last)sL) is %(pct)d%% lower than last week (%(prior)sL).')
            % {'last': last_7, 'prior': prior_7, 'pct': round(abs(change) * 100)},
        )
    elif change >= MILK_TREND_THRESHOLD:
        _upsert(
            farm, seen_keys, 'milk_trend', FarmInsight.Category.MILK, FarmInsight.Severity.INFO,
            _('Milk yield is up'),
            _('This week\'s milk production (%(last)sL) is %(pct)d%% higher than last week (%(prior)sL).')
            % {'last': last_7, 'prior': prior_7, 'pct': round(change * 100)},
        )


def _low_stock(farm, seen_keys):
    for item in InventoryItem.objects.filter(farm=farm):
        if not item.is_low_stock:
            continue
        severity = FarmInsight.Severity.CRITICAL if item.current_stock <= 0 else FarmInsight.Severity.WARNING
        _upsert(
            farm, seen_keys, f'low_stock_{item.id}', FarmInsight.Category.INVENTORY, severity,
            _('%(name)s is low on stock') % {'name': item.name},
            _('%(stock)s %(unit)s left (reorder level: %(level)s).')
            % {'stock': item.current_stock, 'unit': item.get_unit_display(), 'level': item.reorder_level},
        )


def _overdue_tasks(farm, seen_keys):
    today = timezone.localdate()
    overdue = Task.objects.filter(farm=farm, due_date__lt=today).exclude(
        status__in=[Task.Status.DONE, Task.Status.CANCELLED]
    ).order_by('due_date')
    count = overdue.count()
    if not count:
        return
    oldest = overdue.first()
    extra = _(' and %(count)d more.') % {'count': count - 1} if count > 1 else ''
    _upsert(
        farm, seen_keys, 'overdue_tasks', FarmInsight.Category.TASKS, FarmInsight.Severity.WARNING,
        _('%(count)d overdue task(s)') % {'count': count},
        _('"%(title)s" has been overdue since %(date)s%(extra)s')
        % {'title': oldest.title, 'date': oldest.due_date, 'extra': extra},
    )


def _finance_trend(farm, seen_keys):
    today = timezone.localdate()

    def net_between(start, end):
        qs = Transaction.objects.filter(farm=farm, date__gte=start, date__lt=end)
        income = qs.filter(kind=Transaction.Kind.INCOME).aggregate(t=Sum('amount'))['t'] or Decimal('0')
        expense = qs.filter(kind=Transaction.Kind.EXPENSE).aggregate(t=Sum('amount'))['t'] or Decimal('0')
        return income - expense

    last_30 = net_between(today - timedelta(days=29), today + timedelta(days=1))
    prior_30 = net_between(today - timedelta(days=59), today - timedelta(days=29))
    if prior_30 <= 0:
        return  # a near-zero/negative base makes a % swing meaningless, not just noisy
    if last_30 < prior_30 * (1 - FINANCE_TREND_THRESHOLD):
        _upsert(
            farm, seen_keys, 'finance_trend', FarmInsight.Category.FINANCE, FarmInsight.Severity.WARNING,
            _('Net income has dropped'),
            _('Net income over the last 30 days (%(last)s) is well below the prior 30 days (%(prior)s).')
            % {'last': last_30, 'prior': prior_30},
        )


def _upcoming_harvest(farm, seen_keys):
    today = timezone.localdate()
    crops = Crop.objects.filter(farm=farm, expected_harvest__gte=today, expected_harvest__lte=today + timedelta(days=7))
    for crop in crops:
        _upsert(
            farm, seen_keys, f'harvest_{crop.id}', FarmInsight.Category.CROPS, FarmInsight.Severity.INFO,
            _('%(name)s harvest coming up') % {'name': crop.name},
            _('Expected harvest on %(date)s.') % {'date': crop.expected_harvest},
        )


DETECTORS = [_cold_start_tip, _milk_trend, _low_stock, _overdue_tasks, _finance_trend, _upcoming_harvest]


def refresh_insights(farm):
    """Recompute every detector for `farm` and reconcile the stored rows -
    upserting whatever still applies, deleting whatever no longer does.
    Called on every view of the insights page (see insights.views.overview);
    no scheduled job runs this, matching every other "smart" feature in the
    app (see analysis.MilkPrediction, creditscore.CreditScoreSnapshot)."""
    seen_keys = set()
    for detector in DETECTORS:
        detector(farm, seen_keys)
    FarmInsight.objects.filter(farm=farm).exclude(key__in=seen_keys).delete()
    return FarmInsight.objects.filter(farm=farm)
