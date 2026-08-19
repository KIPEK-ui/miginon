from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

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
        messages.success(request, f'{crop.name} added.')
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
        messages.success(request, f'{crop.name} updated.')
        return redirect('crops:crop_detail', crop_id=crop.id)
    return render(request, 'crops/crop_form.html', {'form': form, 'crop': crop})


@edit_delete_required
def crop_delete(request, crop_id):
    crop = get_object_or_404(Crop, id=crop_id, farm=request.farm)
    if request.method == 'POST':
        description = crop.name
        crop.delete()
        notify(request.farm, request.user, Notification.Verb.DELETED, 'crop', description)
        messages.success(request, f'{description} was deleted.')
        return redirect('crops:crop_list')
    return redirect('crops:crop_detail', crop_id=crop.id)


@any_member_required
def activity_list(request):
    activities = CropActivity.objects.filter(farm=request.farm).select_related('crop')[:60]
    return render(request, 'crops/activity_list.html', {'activities': activities})


@log_activity_required
def activity_create(request):
    if not request.farm.crops.exists():
        messages.info(request, 'Add a crop first.')
        return redirect('crops:crop_create')

    form = CropActivityForm(request.POST or None, farm=request.farm)
    if request.method == 'POST' and form.is_valid():
        activity = form.save(commit=False)
        activity.farm = request.farm
        activity.recorded_by = request.user
        activity.save()
        _sync_harvest_movement(activity, request.farm, request.user)
        activity.save(update_fields=['stock_movement'])
        notify(
            request.farm, request.user, Notification.Verb.CREATED, 'crop activity',
            f'{activity.get_activity_type_display()} - {activity.crop.name}'
        )
        messages.success(request, f'{activity.get_activity_type_display()} logged for {activity.crop.name}.')
        return redirect('crops:activity_list')
    return render(request, 'crops/activity_form.html', {'form': form})


@edit_delete_required
def activity_edit(request, activity_id):
    activity = get_object_or_404(CropActivity, id=activity_id, farm=request.farm)
    form = CropActivityForm(request.POST or None, instance=activity, farm=request.farm)
    if request.method == 'POST' and form.is_valid():
        form.save()
        _sync_harvest_movement(activity, request.farm, request.user)
        activity.save(update_fields=['stock_movement'])
        notify(
            request.farm, request.user, Notification.Verb.UPDATED, 'crop activity',
            f'{activity.get_activity_type_display()} - {activity.crop.name}'
        )
        messages.success(request, 'Crop activity updated.')
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
        messages.success(request, 'Crop activity deleted.')
    return redirect('crops:activity_list')
