from .models import InventoryItem, StockMovement


def movement_delta(movement: StockMovement):
    """The signed change this movement made to current_stock. For a
    correction, the delta is fixed relative to the stock level at the time
    it was applied (stock_before), so it stays a valid, order-independent
    undo even if other movements happen later."""
    if movement.movement_type == StockMovement.MovementType.RESTOCK:
        return movement.quantity
    if movement.movement_type == StockMovement.MovementType.USAGE:
        return -movement.quantity
    return movement.quantity - movement.stock_before  # ADJUSTMENT


def apply_movement(movement: StockMovement):
    """Adjust the parent item's current_stock for a newly created movement,
    snapshotting the stock level beforehand so it can be reversed later."""
    item = movement.item
    movement.stock_before = item.current_stock
    movement.save(update_fields=['stock_before'])
    item.current_stock += movement_delta(movement)
    item.save(update_fields=['current_stock'])


def reverse_movement(movement: StockMovement):
    """Undo a movement's effect on its item's current_stock (used before
    deleting a movement)."""
    item = movement.item
    item.current_stock -= movement_delta(movement)
    item.save(update_fields=['current_stock'])


def _get_milk_item(farm):
    item, _ = InventoryItem.objects.get_or_create(
        farm=farm, name='Milk',
        defaults={'category': InventoryItem.Category.PRODUCE, 'unit': InventoryItem.Unit.LITRES},
    )
    return item


def record_milk_production(farm, liters, date, user):
    """Auto-restock the farm's Milk inventory item whenever a MilkRecord is
    logged (see cows.views.milk_create), so on-hand milk stock always
    reflects what's been produced but not yet sold."""
    item = _get_milk_item(farm)
    movement = StockMovement.objects.create(
        farm=farm, item=item, date=date, movement_type=StockMovement.MovementType.RESTOCK,
        quantity=liters, note='Milk production', recorded_by=user,
    )
    apply_movement(movement)
    return movement


def record_milk_sale(farm, liters, date, user):
    """Draw down the farm's Milk inventory item when a sale is recorded
    (see finance.views.milk_sale_create)."""
    item = _get_milk_item(farm)
    movement = StockMovement.objects.create(
        farm=farm, item=item, date=date, movement_type=StockMovement.MovementType.USAGE,
        quantity=liters, note='Milk sale', recorded_by=user,
    )
    apply_movement(movement)
    return movement


def record_milk_internal_use(farm, liters, date, user, note='Internal use', used_by=None):
    """Draw down the farm's Milk inventory item for usage that isn't a sale
    - calves being fed milk, staff consumption, spoilage, etc. (see
    inventory.views.milk_usage_create). Unlike record_milk_sale, this never
    creates a finance transaction: it's a cost/loss of stock, not income -
    without this, that milk would just look like it vanished from
    production vs. sales figures instead of being accounted for."""
    item = _get_milk_item(farm)
    movement = StockMovement.objects.create(
        farm=farm, item=item, date=date, movement_type=StockMovement.MovementType.USAGE,
        quantity=liters, note=note, used_by=used_by, recorded_by=user,
    )
    apply_movement(movement)
    return movement


def record_feed_usage(farm, item_name, kg, date, user):
    """Draw down a feed inventory item (e.g. 'Dairy Meal', 'Silage/Hay')
    whenever a FeedingRecord logs that quantity (see cows.views.feeding_create),
    auto-creating the item on first use - the mirror image of
    record_milk_production, since feeding consumes stock rather than
    producing it."""
    item, _ = InventoryItem.objects.get_or_create(
        farm=farm, name=item_name,
        defaults={'category': InventoryItem.Category.FEED, 'unit': InventoryItem.Unit.KG},
    )
    movement = StockMovement.objects.create(
        farm=farm, item=item, date=date, movement_type=StockMovement.MovementType.USAGE,
        quantity=kg, note='Feeding', recorded_by=user,
    )
    apply_movement(movement)
    return movement


def record_crop_harvest(farm, item_name, kg, date, user):
    """Auto-restock a produce inventory item named after the crop whenever a
    harvesting CropActivity logs a quantity (see crops.views.activity_create)
    - the crop equivalent of record_milk_production."""
    item, _ = InventoryItem.objects.get_or_create(
        farm=farm, name=item_name,
        defaults={'category': InventoryItem.Category.PRODUCE, 'unit': InventoryItem.Unit.KG},
    )
    movement = StockMovement.objects.create(
        farm=farm, item=item, date=date, movement_type=StockMovement.MovementType.RESTOCK,
        quantity=kg, note='Crop harvest', recorded_by=user,
    )
    apply_movement(movement)
    return movement
