from .models import StockMovement


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
