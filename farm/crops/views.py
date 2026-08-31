from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _

from blockchain.models import FiqLedgerEntry
from blockchain.services import FIQ_REWARD_PER_KG_HARVESTED, mint_fiq, mint_harvest_nft
from farms.permissions import (
    any_member_required,
    edit_delete_required,
    log_activity_required,
    manage_records_required,
)
from inventory.services import record_crop_harvest, reverse_movement
from notifications.models import Notification
from notifications.services import notify

from .forms import CropActivityForm, CropForm
from .models import Crop, CropActivity


def _sync_harvest_movement(activity, farm, user):
    """Create/update/clear the produce StockMovement linked to a
    CropActivity, keeping it in sync with activity_type/quantity_harvested_kg
    - same reverse-and-relog reconciliation used for milk (see
    cows.views.milk_edit). Works for both a brand-new activity and an edit,
    including one whose activity_type changes to/from harvesting."""
    old_movement = activity.stock_movement
    if old_movement:
        reverse_movement(old_movement)
        old_movement.delete()
        activity.stock_movement = None

    if activity.activity_type == CropActivity.ActivityType.HARVESTING and activity.quantity_harvested_kg:
        activity.stock_movement = record_crop_harvest(
            farm, activity.crop.name, activity.quantity_harvested_kg, activity.date, user
        )


def _sync_harvest_certificate(activity):
    """Mint a harvest-certificate NFT (plus a proportional FIQ reward) the
    first time this activity becomes a qualifying harvest. Idempotent via
    the hedera_token_id guard - unlike the stock movement this can't be
    meaningfully un-minted/re-minted on a later edit, so once set it's left
    alone even if activity_type later changes away from harvesting (honest
    provenance: this harvest happened and was certified at the time,
    regardless of later reclassification)."""
    if not (
        activity.activity_type == CropActivity.ActivityType.HARVESTING
        and activity.quantity_harvested_kg
        and not activity.hedera_token_id
    ):
        return
    result = mint_harvest_nft(activity)
    if not result:
        return
    activity.hedera_token_id = result['token_id']
    activity.hedera_serial_number = result['serial_number']
    activity.hedera_transaction_id = result['transaction_id']
    activity.hedera_minted_at = timezone.now()
    fiq_amount = activity.quantity_harvested_kg * FIQ_REWARD_PER_KG_HARVESTED
    fiq_result = mint_fiq(fiq_amount)
    if fiq_result:
        FiqLedgerEntry.objects.create(
            farm=activity.farm, amount=fiq_amount, reason=FiqLedgerEntry.Reason.HARVEST_LOGGED,
            hedera_transaction_id=fiq_result['transaction_id'], crop_activity=activity,
        )


@any_member_required
def crop_list(request):
    crops = Crop.objects.filter(farm=request.farm).order_by('-created_at')
    return render(request, 'crops/crop_list.html', {'crops': crops})


@manage_records_required
def crop_create(request):
    form = CropForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        crop = form.save(commit=False)
        crop.farm = request.farm
        crop.added_by = request.user
        crop.save()
        notify(request.farm, request.user, Notification.Verb.CREATED, 'crop', crop.name)
        messages.success(request, _('%(name)s added.') % {'name': crop.name})
        return redirect('crops:crop_list')
    return render(request, 'crops/crop_form.html', {'form': form})


@any_member_required
def crop_detail(request, crop_id):
    crop = get_object_or_404(Crop, id=crop_id, farm=request.farm)
    activities = crop.activities.all()[:30]
    return render(request, 'crops/crop_detail.html', {'crop': crop, 'activities': activities})


@edit_delete_required
def crop_edit(request, crop_id):
    crop = get_object_or_404(Crop, id=crop_id, farm=request.farm)
    form = CropForm(request.POST or None, instance=crop)
    if request.method == 'POST' and form.is_valid():
        form.save()
        notify(request.farm, request.user, Notification.Verb.UPDATED, 'crop', crop.name)
        messages.success(request, _('%(name)s updated.') % {'name': crop.name})
        return redirect('crops:crop_detail', crop_id=crop.id)
    return render(request, 'crops/crop_form.html', {'form': form, 'crop': crop})


@edit_delete_required
def crop_delete(request, crop_id):
    crop = get_object_or_404(Crop, id=crop_id, farm=request.farm)
    if request.method == 'POST':
        description = crop.name
        crop.delete()
        notify(request.farm, request.user, Notification.Verb.DELETED, 'crop', description)
        messages.success(request, _('%(description)s was deleted.') % {'description': description})
        return redirect('crops:crop_list')
    return redirect('crops:crop_detail', crop_id=crop.id)


@any_member_required
def activity_list(request):
    activities = CropActivity.objects.filter(farm=request.farm).select_related('crop')[:60]
    return render(request, 'crops/activity_list.html', {'activities': activities})


@log_activity_required
def activity_create(request):
    if not request.farm.crops.exists():
        messages.info(request, _('Add a crop first.'))
        return redirect('crops:crop_create')

    form = CropActivityForm(request.POST or None, farm=request.farm)
    if request.method == 'POST' and form.is_valid():
        activity = form.save(commit=False)
        activity.farm = request.farm
        activity.recorded_by = request.user
        activity.save()
        _sync_harvest_movement(activity, request.farm, request.user)
        _sync_harvest_certificate(activity)
        activity.save(update_fields=[
            'stock_movement', 'hedera_token_id', 'hedera_serial_number',
            'hedera_transaction_id', 'hedera_minted_at',
        ])
        notify(
            request.farm, request.user, Notification.Verb.CREATED, 'crop activity',
            f'{activity.get_activity_type_display()} - {activity.crop.name}'
        )
        messages.success(
            request,
            _('%(activity)s logged for %(crop)s.')
            % {'activity': activity.get_activity_type_display(), 'crop': activity.crop.name}
        )
        return redirect('crops:activity_list')
    return render(request, 'crops/activity_form.html', {'form': form})


@edit_delete_required
def activity_edit(request, activity_id):
    activity = get_object_or_404(CropActivity, id=activity_id, farm=request.farm)
    form = CropActivityForm(request.POST or None, instance=activity, farm=request.farm)
    if request.method == 'POST' and form.is_valid():
        form.save()
        _sync_harvest_movement(activity, request.farm, request.user)
        _sync_harvest_certificate(activity)
        activity.save(update_fields=[
            'stock_movement', 'hedera_token_id', 'hedera_serial_number',
            'hedera_transaction_id', 'hedera_minted_at',
        ])
        notify(
            request.farm, request.user, Notification.Verb.UPDATED, 'crop activity',
            f'{activity.get_activity_type_display()} - {activity.crop.name}'
        )
        messages.success(request, _('Crop activity updated.'))
        return redirect('crops:activity_list')
    return render(request, 'crops/activity_form.html', {'form': form, 'activity': activity})


@edit_delete_required
def activity_delete(request, activity_id):
    activity = get_object_or_404(CropActivity, id=activity_id, farm=request.farm)
    if request.method == 'POST':
        description = f'{activity.get_activity_type_display()} - {activity.crop.name}'
        if activity.stock_movement:
            reverse_movement(activity.stock_movement)
            activity.stock_movement.delete()
        activity.delete()
        notify(request.farm, request.user, Notification.Verb.DELETED, 'crop activity', description)
        messages.success(request, _('Crop activity deleted.'))
    return redirect('crops:activity_list')
