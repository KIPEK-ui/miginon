from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from farms.models import FarmMembership
from farms.permissions import (
    any_member_required,
    edit_delete_required,
    log_activity_required,
    manage_records_required,
)
from notifications.models import Notification
from notifications.services import notify

from .feed_reference import REFERENCE_INGREDIENTS, suggest_composition
from .forms import InventoryItemForm, MilkUsageForm, StockMovementForm
from .models import FeedComposition, InventoryItem, StockMovement
from .services import apply_movement, record_milk_internal_use, reverse_movement


@any_member_required
def item_list(request):
    items = InventoryItem.objects.filter(farm=request.farm).order_by('name')
    return render(request, 'inventory/item_list.html', {'items': items})


@manage_records_required
def item_create(request):
    form = InventoryItemForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        item = form.save(commit=False)
        item.farm = request.farm
        item.added_by = request.user
        item.save()
        notify(request.farm, request.user, Notification.Verb.CREATED, 'inventory item', item.name)
        messages.success(request, f'{item.name} added to inventory.')
        return redirect('inventory:item_list')
    return render(request, 'inventory/item_form.html', {'form': form})


@any_member_required
def item_detail(request, item_id):
    item = get_object_or_404(InventoryItem, id=item_id, farm=request.farm)
    movements = item.movements.select_related('used_by__user').all()[:30]
    composition = FeedComposition.objects.filter(item=item).first()
    return render(request, 'inventory/item_detail.html', {
        'item': item, 'movements': movements, 'composition': composition,
    })


@edit_delete_required
def item_composition(request, item_id):
    item = get_object_or_404(InventoryItem, id=item_id, farm=request.farm)
    composition, _ = FeedComposition.objects.get_or_create(item=item)

    suggested = None
    if request.method == 'GET' and request.GET.get('target_protein'):
        try:
            target = float(request.GET['target_protein'])
            ingredients, achieved = suggest_composition(target)
            suggested = {'ingredients': ingredients, 'achieved_protein_pct': achieved, 'target': target}
        except (ValueError, TypeError):
            messages.error(request, 'Enter a valid target protein percentage.')

    if request.method == 'POST':
        names = request.POST.getlist('ingredient_name')
        percents = request.POST.getlist('ingredient_percent')
        ingredients = []
        for name, percent in zip(names, percents):
            name = name.strip()
            if not name or not percent.strip():
                continue
            try:
                ingredients.append({'name': name, 'percent': float(percent)})
            except ValueError:
                continue

        crude_protein_raw = request.POST.get('crude_protein_pct', '').strip()
        composition.ingredients = ingredients
        composition.crude_protein_pct = crude_protein_raw or None
        composition.save()
        notify(request.farm, request.user, Notification.Verb.UPDATED, 'feed composition', item.name)
        messages.success(request, f'Composition saved for {item.name}.')
        return redirect('inventory:item_detail', item_id=item.id)

    ROW_COUNT = 8
    source_ingredients = suggested['ingredients'] if suggested else composition.ingredients
    ingredient_rows = [
        {'name': ing.get('name', ''), 'percent': ing.get('percent', '')}
        for ing in source_ingredients[:ROW_COUNT]
    ]
    while len(ingredient_rows) < ROW_COUNT:
        ingredient_rows.append({'name': '', 'percent': ''})

    return render(request, 'inventory/composition_form.html', {
        'item': item, 'composition': composition, 'suggested': suggested,
        'ingredient_rows': ingredient_rows, 'reference_ingredients': REFERENCE_INGREDIENTS,
    })


@edit_delete_required
def item_edit(request, item_id):
    item = get_object_or_404(InventoryItem, id=item_id, farm=request.farm)
    form = InventoryItemForm(request.POST or None, instance=item, lock_stock=True)
    if request.method == 'POST' and form.is_valid():
        form.save()
        notify(request.farm, request.user, Notification.Verb.UPDATED, 'inventory item', item.name)
        messages.success(request, f'{item.name} updated.')
        return redirect('inventory:item_detail', item_id=item.id)
    return render(request, 'inventory/item_form.html', {'form': form, 'item': item})


@edit_delete_required
def item_delete(request, item_id):
    item = get_object_or_404(InventoryItem, id=item_id, farm=request.farm)
    if request.method == 'POST':
        description = item.name
        item.delete()
        notify(request.farm, request.user, Notification.Verb.DELETED, 'inventory item', description)
        messages.success(request, f'{description} was deleted.')
        return redirect('inventory:item_list')
    return redirect('inventory:item_detail', item_id=item.id)


@any_member_required
def movement_list(request):
    movements = StockMovement.objects.filter(farm=request.farm).select_related('item', 'used_by__user')[:60]
    return render(request, 'inventory/movement_list.html', {'movements': movements})


@log_activity_required
def movement_create(request):
    if not request.farm.inventory_items.exists():
        messages.info(request, 'Add an inventory item first.')
        return redirect('inventory:item_create')

    form = StockMovementForm(request.POST or None, farm=request.farm)
    if request.method == 'POST' and form.is_valid():
        movement = form.save(commit=False)
        movement.farm = request.farm
        movement.recorded_by = request.user
        movement.save()
        was_low_stock = movement.item.is_low_stock
        apply_movement(movement)
        notify(
            request.farm, request.user, Notification.Verb.CREATED, 'stock movement',
            f'{movement.item.name} - {movement.get_movement_type_display()} {movement.quantity}'
        )
        if movement.item.is_low_stock and not was_low_stock:
            managers = request.farm.memberships.filter(status=FarmMembership.Status.ACTIVE).select_related('user')
            for m in managers:
                if m.can_manage_workers and m.user_id != request.user.id:
                    notify(
                        request.farm, request.user, Notification.Verb.UPDATED, 'inventory item',
                        f'{movement.item.name} is low on stock ({movement.item.current_stock} {movement.item.unit} left)',
                        recipient=m.user,
                    )
        messages.success(request, f'{movement.get_movement_type_display()} recorded for {movement.item.name}.')
        return redirect('inventory:movement_list')
    return render(request, 'inventory/movement_form.html', {'form': form})


@log_activity_required
def milk_usage_create(request):
    """Log milk that left the farm without being sold - fed to calves,
    consumed by staff, spoiled, etc. Draws down the same Milk inventory
    item as a sale would (so stock stays accurate), but never touches
    finance - it's the internal-use counterpart to finance.milk_sale_create."""
    form = MilkUsageForm(request.POST or None, farm=request.farm)
    if request.method == 'POST' and form.is_valid():
        liters = form.cleaned_data['liters']
        date = form.cleaned_data['date']
        used_by = form.cleaned_data['used_by']
        note_detail = form.cleaned_data['note']
        purpose_label = dict(MilkUsageForm.PURPOSE_CHOICES)[form.cleaned_data['purpose']]
        description = f'{purpose_label} - {liters}L' + (f' ({note_detail})' if note_detail else '')

        milk_item = InventoryItem.objects.filter(farm=request.farm, name='Milk').first()
        stock_before = milk_item.current_stock if milk_item else 0

        record_milk_internal_use(request.farm, liters, date, request.user, note=description, used_by=used_by)
        notify(request.farm, request.user, Notification.Verb.CREATED, 'milk usage', description)
        messages.success(request, f'{description} recorded.')
        if stock_before - liters < 0:
            messages.warning(request, 'Milk stock is now negative - check for missing production records.')
        return redirect('inventory:movement_list')
    return render(request, 'inventory/milk_usage_form.html', {'form': form})


@edit_delete_required
def movement_delete(request, movement_id):
    """Stock movements are a ledger, not freestanding records - to fix a
    mistake, remove the wrong entry and log a correct one rather than
    editing history in place."""
    movement = get_object_or_404(StockMovement, id=movement_id, farm=request.farm)
    if request.method == 'POST':
        description = f'{movement.item.name} - {movement.get_movement_type_display()} {movement.quantity}'
        reverse_movement(movement)
        movement.delete()
        notify(request.farm, request.user, Notification.Verb.DELETED, 'stock movement', description)
        messages.success(request, 'Stock movement deleted and stock level restored.')
    return redirect('inventory:movement_list')
