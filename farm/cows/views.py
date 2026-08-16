from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from farms.permissions import (
    any_member_required,
    edit_delete_required,
    manage_herd_required,
    record_production_required,
)
from notifications.models import Notification
from notifications.services import notify

from .forms import CowForm, CowTransferForm, FeedingRecordForm, MilkRecordForm
from .models import Cow, CowTransfer, FeedingRecord, MilkRecord


@any_member_required
def cow_list(request):
    cows = Cow.objects.filter(farm=request.farm).select_related('block').order_by('block__name', 'tag_id')
    return render(request, 'cows/cow_list.html', {'cows': cows})


@manage_herd_required
def cow_create(request):
    form = CowForm(request.POST or None, farm=request.farm)
    if request.method == 'POST' and form.is_valid():
        cow = form.save(commit=False)
        cow.farm = request.farm
        cow.added_by = request.user
        cow.save()
        notify(request.farm, request.user, Notification.Verb.CREATED, 'cow', str(cow))
        messages.success(request, f'{cow} added to {cow.block.name}.')
        return redirect('cows:cow_list')
    return render(request, 'cows/cow_form.html', {'form': form})


@any_member_required
def cow_detail(request, cow_id):
    cow = get_object_or_404(Cow, id=cow_id, farm=request.farm)
    transfers = cow.transfers.select_related('from_block', 'to_block')[:10]
    return render(request, 'cows/cow_detail.html', {'cow': cow, 'transfers': transfers})


@edit_delete_required
def cow_edit(request, cow_id):
    cow = get_object_or_404(Cow, id=cow_id, farm=request.farm)
    form = CowForm(request.POST or None, instance=cow, farm=request.farm)
    if request.method == 'POST' and form.is_valid():
        form.save()
        notify(request.farm, request.user, Notification.Verb.UPDATED, 'cow', str(cow))
        messages.success(request, f'{cow} updated.')
        return redirect('cows:cow_detail', cow_id=cow.id)
    return render(request, 'cows/cow_form.html', {'form': form, 'cow': cow})


@edit_delete_required
def cow_delete(request, cow_id):
    cow = get_object_or_404(Cow, id=cow_id, farm=request.farm)
    if request.method == 'POST':
        description = str(cow)
        cow.delete()
        notify(request.farm, request.user, Notification.Verb.DELETED, 'cow', description)
        messages.success(request, f'{description} was deleted.')
        return redirect('cows:cow_list')
    return redirect('cows:cow_detail', cow_id=cow.id)


@manage_herd_required
def cow_transfer(request, cow_id):
    cow = get_object_or_404(Cow, id=cow_id, farm=request.farm)
    if not request.farm.blocks.exclude(id=cow.block_id).exists():
        messages.info(request, 'Add another block first to transfer cows between blocks.')
        return redirect('cows:cow_detail', cow_id=cow.id)

    form = CowTransferForm(request.POST or None, cow=cow)
    if request.method == 'POST' and form.is_valid():
        to_block = form.cleaned_data['to_block']
        from_block = cow.block
        CowTransfer.objects.create(
            farm=request.farm,
            cow=cow,
            from_block=from_block,
            to_block=to_block,
            note=form.cleaned_data['note'],
            transferred_by=request.user,
        )
        cow.block = to_block
        cow.save(update_fields=['block'])
        notify(
            request.farm, request.user, Notification.Verb.UPDATED, 'cow',
            f'{cow.tag_id} moved from {from_block.name} to {to_block.name}'
        )
        messages.success(request, f'{cow} moved to {to_block.name}.')
        return redirect('cows:cow_detail', cow_id=cow.id)
    return render(request, 'cows/cow_transfer.html', {'form': form, 'cow': cow})


@any_member_required
def feeding_list(request):
    records = FeedingRecord.objects.filter(farm=request.farm).select_related('block').prefetch_related('cows')[:60]
    return render(request, 'cows/feeding_list.html', {'records': records})


def _feeding_form_context(request, form, record=None):
    farm_cows = (
        request.farm.cows.filter(status=Cow.Status.ACTIVE).select_related('block').order_by('block__name', 'tag_id')
    )
    if request.method == 'POST':
        selected_cow_ids = {int(pk) for pk in request.POST.getlist('cows') if pk.isdigit()}
    elif record is not None:
        selected_cow_ids = set(record.cows.values_list('id', flat=True))
    else:
        selected_cow_ids = set()
    return {'form': form, 'farm_cows': farm_cows, 'selected_cow_ids': selected_cow_ids, 'record': record}


@record_production_required
def feeding_create(request):
    if not request.farm.cows.filter(status=Cow.Status.ACTIVE).exists():
        messages.info(request, 'Add an active cow first.')
        return redirect('cows:cow_create')

    form = FeedingRecordForm(request.POST or None, farm=request.farm)
    if request.method == 'POST' and form.is_valid():
        record = form.save(commit=False)
        record.farm = request.farm
        record.recorded_by = request.user
        record.save()
        form.save_m2m()
        record.cows_count = record.cows.count()
        record.save(update_fields=['cows_count'])
        notify(
            request.farm, request.user, Notification.Verb.CREATED, 'feeding record',
            f'{record.block.name} - {record.date} {record.get_session_display()}'
        )
        messages.success(request, f'Feeding record saved for {record.block.name} ({record.get_session_display()}).')
        return redirect('cows:feeding_list')

    return render(request, 'cows/feeding_form.html', _feeding_form_context(request, form))


@edit_delete_required
def feeding_edit(request, record_id):
    record = get_object_or_404(FeedingRecord, id=record_id, farm=request.farm)
    form = FeedingRecordForm(request.POST or None, instance=record, farm=request.farm)
    if request.method == 'POST' and form.is_valid():
        updated = form.save()
        form.save_m2m()
        updated.cows_count = updated.cows.count()
        updated.save(update_fields=['cows_count'])
        notify(
            request.farm, request.user, Notification.Verb.UPDATED, 'feeding record',
            f'{updated.block.name} - {updated.date} {updated.get_session_display()}'
        )
        messages.success(request, 'Feeding record updated.')
        return redirect('cows:feeding_list')

    return render(request, 'cows/feeding_form.html', _feeding_form_context(request, form, record))


@edit_delete_required
def feeding_delete(request, record_id):
    record = get_object_or_404(FeedingRecord, id=record_id, farm=request.farm)
    if request.method == 'POST':
        description = f'{record.block.name} - {record.date} {record.get_session_display()}'
        record.delete()
        notify(request.farm, request.user, Notification.Verb.DELETED, 'feeding record', description)
        messages.success(request, 'Feeding record deleted.')
    return redirect('cows:feeding_list')


@any_member_required
def milk_list(request):
    records = MilkRecord.objects.filter(farm=request.farm).select_related('cow', 'block')[:60]
    return render(request, 'cows/milk_list.html', {'records': records})


@record_production_required
def milk_create(request):
    if not request.farm.cows.filter(status=Cow.Status.ACTIVE).exists():
        messages.info(request, 'Add an active cow first.')
        return redirect('cows:cow_create')

    form = MilkRecordForm(request.POST or None, farm=request.farm)
    if request.method == 'POST' and form.is_valid():
        record = form.save(commit=False)
        record.farm = request.farm
        record.block = record.cow.block
        record.recorded_by = request.user
        record.save()
        notify(
            request.farm, request.user, Notification.Verb.CREATED, 'milk record',
            f'{record.cow.tag_id} - {record.date} {record.get_session_display()} - {record.liters}L'
        )
        messages.success(request, f'Milk record saved for {record.cow} ({record.get_session_display()}).')
        return redirect('cows:milk_list')
    return render(request, 'cows/milk_form.html', {'form': form})


@edit_delete_required
def milk_edit(request, record_id):
    record = get_object_or_404(MilkRecord, id=record_id, farm=request.farm)
    form = MilkRecordForm(request.POST or None, instance=record, farm=request.farm)
    if request.method == 'POST' and form.is_valid():
        updated = form.save(commit=False)
        updated.block = updated.cow.block
        updated.save()
        notify(
            request.farm, request.user, Notification.Verb.UPDATED, 'milk record',
            f'{updated.cow.tag_id} - {updated.date} {updated.get_session_display()} - {updated.liters}L'
        )
        messages.success(request, 'Milk record updated.')
        return redirect('cows:milk_list')
    return render(request, 'cows/milk_form.html', {'form': form, 'record': record})


@edit_delete_required
def milk_delete(request, record_id):
    record = get_object_or_404(MilkRecord, id=record_id, farm=request.farm)
    if request.method == 'POST':
        description = f'{record.cow.tag_id} - {record.date} {record.get_session_display()} - {record.liters}L'
        record.delete()
        notify(request.farm, request.user, Notification.Verb.DELETED, 'milk record', description)
        messages.success(request, 'Milk record deleted.')
    return redirect('cows:milk_list')
