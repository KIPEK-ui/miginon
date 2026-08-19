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

from .forms import InventoryItemForm, StockMovementForm
from .models import InventoryItem, StockMovement
from .services import apply_movement, reverse_movement


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
    movements = item.movements.all()[:30]
    return render(request, 'inventory/item_detail.html', {'item': item, 'movements': movements})


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
    movements = StockMovement.objects.filter(farm=request.farm).select_related('item')[:60]
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
