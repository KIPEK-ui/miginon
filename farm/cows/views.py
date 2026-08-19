from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from core.email import send_styled_email_safely
from farms.permissions import (
    any_member_required,
    edit_delete_required,
    manage_herd_required,
    record_production_required,
)
from inventory.services import record_feed_usage, record_milk_production, reverse_movement
from notifications.models import Notification
from notifications.services import notify

from .forms import CowForm, CowTransferForm, FeedingRecordForm, MilkRecordForm
from .models import Cow, CowTransfer, FeedingRecord, FeedingRecordCow, MilkRecord


@any_member_required
def cow_list(request):
    cows = list(
        Cow.objects.filter(farm=request.farm).select_related('block').order_by('block__name', 'tag_id')
    )
    groups = []
    for value, label in [
        (Cow.Category.COW, 'Cows'),
        (Cow.Category.HEIFER, 'Heifers'),
        (Cow.Category.CALF, 'Calves'),
        (Cow.Category.BULL, 'Bulls'),
    ]:
        group_cows = [c for c in cows if c.category == value]
        if group_cows:
            groups.append({'label': label, 'cows': group_cows})
    return render(request, 'cows/cow_list.html', {'cows': cows, 'groups': groups})


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
    farm_cows = list(
        request.farm.cows.filter(status=Cow.Status.ACTIVE).select_related('block').order_by('block__name', 'tag_id')
    )
    if request.method == 'POST':
        selected_cow_ids = {int(pk) for pk in request.POST.getlist('cows') if pk.isdigit()}
    elif record is not None:
        selected_cow_ids = set(record.cows.values_list('id', flat=True))
    else:
        selected_cow_ids = set()

    if record is not None and request.method != 'POST':
        allocations_by_cow = {a.cow_id: a for a in record.allocations.all()}
        for cow in farm_cows:
            alloc = allocations_by_cow.get(cow.id)
            cow.alloc_dairy_kg = alloc.dairy_meal_kg if alloc else None
            cow.alloc_silage_kg = alloc.silage_hay_kg if alloc else None
    else:
        for cow in farm_cows:
            cow.alloc_dairy_kg = None
            cow.alloc_silage_kg = None

    return {'form': form, 'farm_cows': farm_cows, 'selected_cow_ids': selected_cow_ids, 'record': record}


def _sync_feeding_cows(record, cows, dairy_total, silage_total, post_data):
    """Create/update the per-cow FeedingRecordCow rows for the selected
    cows. A farmer who just fills in the block totals gets an even split
    automatically; one who fills in the optional per-cow override inputs
    (named cow_dairy_<id>/cow_silage_<id> - see feeding_form.html's
    "Customize per-cow amounts" section) gets exactly what they typed.
    Cows that were deselected on an edit have their row removed."""
    cow_ids = {c.id for c in cows}
    record.allocations.exclude(cow_id__in=cow_ids).delete()

    count = len(cows) or 1
    even_dairy = dairy_total / count
    even_silage = silage_total / count

    def _parse(raw, fallback):
        raw = (raw or '').strip()
        if not raw:
            return fallback
        try:
            return Decimal(raw)
        except InvalidOperation:
            return fallback

    for cow in cows:
        dairy_kg = _parse(post_data.get(f'cow_dairy_{cow.id}'), even_dairy)
        silage_kg = _parse(post_data.get(f'cow_silage_{cow.id}'), even_silage)
        FeedingRecordCow.objects.update_or_create(
            feeding_record=record, cow=cow,
            defaults={'dairy_meal_kg': dairy_kg, 'silage_hay_kg': silage_kg},
        )


def _sync_feed_movement(record, quantity_field, movement_field, item_name, farm, user):
    """Create/update/clear the StockMovement linked to one of a
    FeedingRecord's feed quantity fields, keeping it in sync with the
    current value - same reverse-and-relog reconciliation used for milk
    (see milk_edit). Works for both a brand-new record (no old movement to
    reverse) and an edit."""
    old_movement = getattr(record, movement_field)
    if old_movement:
        reverse_movement(old_movement)
        old_movement.delete()
        setattr(record, movement_field, None)

    kg = getattr(record, quantity_field)
    if kg and kg > 0:
        movement = record_feed_usage(farm, item_name, kg, record.date, user)
        setattr(record, movement_field, movement)


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
        cows = list(form.cleaned_data['cows'])
        _sync_feeding_cows(record, cows, record.dairy_meal_kg, record.silage_hay_kg, request.POST)
        record.cows_count = len(cows)
        _sync_feed_movement(record, 'dairy_meal_kg', 'dairy_meal_movement', 'Dairy Meal', request.farm, request.user)
        _sync_feed_movement(record, 'silage_hay_kg', 'silage_hay_movement', 'Silage/Hay', request.farm, request.user)
        record.save(update_fields=['cows_count', 'dairy_meal_movement', 'silage_hay_movement'])
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
        updated = form.save(commit=False)
        updated.save()
        cows = list(form.cleaned_data['cows'])
        _sync_feeding_cows(updated, cows, updated.dairy_meal_kg, updated.silage_hay_kg, request.POST)
        updated.cows_count = len(cows)
        _sync_feed_movement(updated, 'dairy_meal_kg', 'dairy_meal_movement', 'Dairy Meal', request.farm, request.user)
        _sync_feed_movement(updated, 'silage_hay_kg', 'silage_hay_movement', 'Silage/Hay', request.farm, request.user)
        updated.save(update_fields=['cows_count', 'dairy_meal_movement', 'silage_hay_movement'])
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
        for movement in (record.dairy_meal_movement, record.silage_hay_movement):
            if movement:
                reverse_movement(movement)
                movement.delete()
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
        movement = record_milk_production(request.farm, record.liters, record.date, request.user)
        record.stock_movement = movement
        record.save(update_fields=['stock_movement'])
        notify(
            request.farm, request.user, Notification.Verb.CREATED, 'milk record',
            f'{record.cow.tag_id} - {record.date} {record.get_session_display()} - {record.liters}L'
        )
        if MilkRecord.objects.filter(farm=request.farm).count() == 1:
            send_styled_email_safely(
                to=request.farm.owner.email,
                subject=f'🎉 First milk record logged on {request.farm.name}!',
                template_name='emails/milestone.html',
                context={
                    'farm': request.farm,
                    'title': 'First milk record logged!',
                    'description': (
                        f'{record.cow} just produced its first recorded {record.liters}L on Farm IQ. '
                        'Every record from here builds your farm\'s production history.'
                    ),
                    'dashboard_url': request.build_absolute_uri(reverse('farms:dashboard')),
                },
            )
        messages.success(request, f'Milk record saved for {record.cow} ({record.get_session_display()}).')
        return redirect('cows:milk_list')
    return render(request, 'cows/milk_form.html', {'form': form})


@edit_delete_required
def milk_edit(request, record_id):
    record = get_object_or_404(MilkRecord, id=record_id, farm=request.farm)
    form = MilkRecordForm(request.POST or None, instance=record, farm=request.farm)
    if request.method == 'POST' and form.is_valid():
        old_movement = record.stock_movement
        updated = form.save(commit=False)
        updated.block = updated.cow.block
        updated.save()

        # Stock movements are a ledger, not freestanding records (see
        # inventory.views.movement_delete) - reconcile by reversing whatever
        # this record produced before and logging a fresh one for the
        # updated liters/date, rather than editing the movement in place.
        if old_movement:
            reverse_movement(old_movement)
            old_movement.delete()
        new_movement = record_milk_production(request.farm, updated.liters, updated.date, request.user)
        updated.stock_movement = new_movement
        updated.save(update_fields=['stock_movement'])

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
        if record.stock_movement:
            reverse_movement(record.stock_movement)
            record.stock_movement.delete()
        record.delete()
        notify(request.farm, request.user, Notification.Verb.DELETED, 'milk record', description)
        messages.success(request, 'Milk record deleted.')
    return redirect('cows:milk_list')
