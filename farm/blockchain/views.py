from datetime import date, timedelta

from django.contrib import messages
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _

from cows.models import FeedingRecord, MilkRecord
from crops.models import CropActivity
from farms.models import FarmMembership, FarmRole
from farms.permissions import any_member_required, manage_records_required
from inventory.models import StockMovement

from .models import FiqLedgerEntry, MilkProductionCertificate
from .services import FIQ_REWARD_PER_DATA_RECORD, FIQ_REWARD_PER_LITER, mint_fiq


@any_member_required
def wallet_view(request):
    farm = request.farm
    balance = FiqLedgerEntry.objects.filter(farm=farm).aggregate(total=Sum('amount'))['total'] or 0
    ledger = FiqLedgerEntry.objects.filter(farm=farm).select_related('cow', 'crop_activity', 'task', 'earned_by')[:50]
    certificates = MilkProductionCertificate.objects.filter(farm=farm)[:20]
    top_contributors = (
        FiqLedgerEntry.objects.filter(farm=farm, earned_by__isnull=False)
        .values('earned_by__first_name', 'earned_by__last_name')
        .annotate(total=Sum('amount'))
        .order_by('-total')[:10]
    )
    workers = FarmMembership.objects.filter(
        farm=farm, status=FarmMembership.Status.ACTIVE
    ).exclude(role=FarmRole.FARMER).select_related('user')
    return render(request, 'blockchain/wallet.html', {
        'balance': balance,
        'ledger': ledger,
        'certificates': certificates,
        'top_contributors': top_contributors,
        'workers': workers,
        'default_start': date.today() - timedelta(days=30),
        'default_end': date.today(),
    })


@manage_records_required
def certificate_create(request):
    if request.method != 'POST':
        return redirect('blockchain:wallet')

    farm = request.farm
    start_date = request.POST.get('start_date')
    end_date = request.POST.get('end_date')
    try:
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
    except (TypeError, ValueError):
        messages.error(request, _('Enter a valid date range.'))
        return redirect('blockchain:wallet')

    if start > end:
        messages.error(request, _('Start date must be before the end date.'))
        return redirect('blockchain:wallet')

    total_liters = MilkRecord.objects.filter(
        farm=farm, date__gte=start, date__lte=end
    ).aggregate(total=Sum('liters'))['total'] or 0

    if not total_liters:
        messages.error(request, _('No milk records found for that date range.'))
        return redirect('blockchain:wallet')

    fiq_amount = total_liters * FIQ_REWARD_PER_LITER
    result = mint_fiq(fiq_amount)
    if not result:
        messages.error(request, _("Couldn't reach Hedera to mint this certificate. Please try again shortly."))
        return redirect('blockchain:wallet')

    certificate = MilkProductionCertificate.objects.create(
        farm=farm, start_date=start, end_date=end, total_liters=total_liters,
        fiq_amount=fiq_amount, hedera_transaction_id=result['transaction_id'], created_by=request.user,
    )
    FiqLedgerEntry.objects.create(
        farm=farm, amount=fiq_amount, reason=FiqLedgerEntry.Reason.MILK_CERTIFICATE,
        hedera_transaction_id=result['transaction_id'], milk_certificate=certificate,
    )
    messages.success(
        request,
        _('Certificate minted for %(liters)sL - %(fiq)s FIQ earned.') % {'liters': total_liters, 'fiq': fiq_amount}
    )
    return redirect('blockchain:wallet')


@manage_records_required
def worker_reward_create(request):
    """Batched FIQ reward for a worker's logged records (milk, feeding,
    crop activity, stock movements) over a date range - never minted per
    record, matching the same reasoning as the milk certificate above (a
    fast data-entry workflow shouldn't carry a live Hedera transaction on
    every log). A manager/farmer picks the worker and period; nothing
    prevents picking overlapping periods twice, same trust model as the
    milk certificate."""
    if request.method != 'POST':
        return redirect('blockchain:wallet')

    farm = request.farm
    membership = get_object_or_404(FarmMembership, id=request.POST.get('worker_id'), farm=farm)
    worker_user = membership.user
    try:
        start = date.fromisoformat(request.POST.get('start_date', ''))
        end = date.fromisoformat(request.POST.get('end_date', ''))
    except (TypeError, ValueError):
        messages.error(request, _('Enter a valid date range.'))
        return redirect('blockchain:wallet')

    if start > end:
        messages.error(request, _('Start date must be before the end date.'))
        return redirect('blockchain:wallet')

    record_count = (
        MilkRecord.objects.filter(farm=farm, recorded_by=worker_user, date__gte=start, date__lte=end).count()
        + FeedingRecord.objects.filter(farm=farm, recorded_by=worker_user, date__gte=start, date__lte=end).count()
        + CropActivity.objects.filter(farm=farm, recorded_by=worker_user, date__gte=start, date__lte=end).count()
        + StockMovement.objects.filter(farm=farm, recorded_by=worker_user, date__gte=start, date__lte=end).count()
    )
    if not record_count:
        messages.error(request, _('No records logged by %(name)s in that date range.') % {'name': worker_user.get_full_name()})
        return redirect('blockchain:wallet')

    fiq_amount = FIQ_REWARD_PER_DATA_RECORD * record_count
    result = mint_fiq(fiq_amount)
    if not result:
        messages.error(request, _("Couldn't reach Hedera to mint this reward. Please try again shortly."))
        return redirect('blockchain:wallet')

    FiqLedgerEntry.objects.create(
        farm=farm, amount=fiq_amount, reason=FiqLedgerEntry.Reason.DATA_RECORDED,
        hedera_transaction_id=result['transaction_id'], earned_by=worker_user,
        period_start=start, period_end=end, record_count=record_count,
    )
    messages.success(
        request,
        _('%(fiq)s FIQ awarded to %(name)s for %(count)s logged records.') % {
            'fiq': fiq_amount, 'name': worker_user.get_full_name(), 'count': record_count,
        }
    )
    return redirect('blockchain:wallet')
