from decimal import Decimal

from django.test import TestCase

from accounts.models import User
from farms.models import Farm, FarmMembership, FarmRole

from .models import InventoryItem, StockMovement
from .services import apply_movement, movement_delta, reverse_movement


class LedgerServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='farmer@example.com', first_name='Fay')
        self.farm = Farm.objects.create(name='Stock Farm', owner=self.user)
        self.item = InventoryItem.objects.create(
            farm=self.farm, name='Dairy Meal', category=InventoryItem.Category.FEED,
            current_stock=Decimal('50.00'),
        )

    def _movement(self, movement_type, quantity):
        return StockMovement.objects.create(
            farm=self.farm, item=self.item, date='2026-01-05',
            movement_type=movement_type, quantity=quantity, recorded_by=self.user,
        )

    def test_restock_increases_stock_and_snapshots_before(self):
        movement = self._movement(StockMovement.MovementType.RESTOCK, Decimal('20.00'))
        apply_movement(movement)
        self.item.refresh_from_db()
        movement.refresh_from_db()
        self.assertEqual(self.item.current_stock, Decimal('70.00'))
        self.assertEqual(movement.stock_before, Decimal('50.00'))

    def test_usage_decreases_stock(self):
        movement = self._movement(StockMovement.MovementType.USAGE, Decimal('15.00'))
        apply_movement(movement)
        self.item.refresh_from_db()
        self.assertEqual(self.item.current_stock, Decimal('35.00'))

    def test_adjustment_sets_absolute_level(self):
        movement = self._movement(StockMovement.MovementType.ADJUSTMENT, Decimal('12.00'))
        apply_movement(movement)
        self.item.refresh_from_db()
        self.assertEqual(self.item.current_stock, Decimal('12.00'))
        self.assertEqual(movement_delta(movement), Decimal('12.00') - Decimal('50.00'))

    def test_reverse_movement_undoes_a_restock(self):
        movement = self._movement(StockMovement.MovementType.RESTOCK, Decimal('20.00'))
        apply_movement(movement)
        reverse_movement(movement)
        self.item.refresh_from_db()
        self.assertEqual(self.item.current_stock, Decimal('50.00'))

    def test_reverse_movement_undoes_a_usage(self):
        movement = self._movement(StockMovement.MovementType.USAGE, Decimal('15.00'))
        apply_movement(movement)
        reverse_movement(movement)
        self.item.refresh_from_db()
        self.assertEqual(self.item.current_stock, Decimal('50.00'))


class InventoryPermissionTests(TestCase):
    def setUp(self):
        self.farmer = User.objects.create_user(email='farmer@example.com', first_name='Fay')
        self.worker = User.objects.create_user(email='worker@example.com', first_name='Wes')
        self.farm = Farm.objects.create(name='Stock Farm', owner=self.farmer)
        FarmMembership.objects.create(user=self.farmer, farm=self.farm, role=FarmRole.FARMER)
        FarmMembership.objects.create(user=self.worker, farm=self.farm, role=FarmRole.WORKER)
        self.item = InventoryItem.objects.create(
            farm=self.farm, name='Dairy Meal', category=InventoryItem.Category.FEED,
            current_stock=Decimal('50.00'),
        )

    def _login(self, user):
        self.client.force_login(user)
        session = self.client.session
        session['active_farm_id'] = self.farm.id
        session.save()

    def test_worker_cannot_create_an_item(self):
        self._login(self.worker)
        self.client.post('/inventory/add/', {
            'name': 'New Item', 'category': InventoryItem.Category.OTHER,
            'unit': InventoryItem.Unit.KG, 'current_stock': '0', 'reorder_level': '0',
        })
        self.assertFalse(InventoryItem.objects.filter(farm=self.farm, name='New Item').exists())

    def test_worker_can_log_a_stock_movement(self):
        self._login(self.worker)
        response = self.client.post('/inventory/movements/add/', {
            'item': self.item.id, 'date': '2026-01-05', 'movement_type': StockMovement.MovementType.RESTOCK,
            'quantity': '10.00', 'used_by': '', 'note': '',
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        self.item.refresh_from_db()
        self.assertEqual(self.item.current_stock, Decimal('60.00'))

    def test_worker_cannot_delete_a_movement(self):
        movement = StockMovement.objects.create(
            farm=self.farm, item=self.item, date='2026-01-05',
            movement_type=StockMovement.MovementType.RESTOCK, quantity=Decimal('10.00'),
        )
        apply_movement(movement)
        self._login(self.worker)
        self.client.post(f'/inventory/movements/{movement.id}/delete/')
        self.assertTrue(StockMovement.objects.filter(id=movement.id).exists())

    def test_low_stock_notifies_managers_not_the_actor(self):
        from notifications.models import Notification

        self.item.reorder_level = Decimal('45.00')
        self.item.save(update_fields=['reorder_level'])
        self._login(self.farmer)
        self.client.post('/inventory/movements/add/', {
            'item': self.item.id, 'date': '2026-01-05', 'movement_type': StockMovement.MovementType.USAGE,
            'quantity': '10.00', 'used_by': '', 'note': '',
        })
        low_stock_notifs = Notification.objects.filter(farm=self.farm, kind='inventory item', recipient=self.farmer)
        # The actor themself is excluded (m.user_id != request.user.id in
        # inventory.views.movement_create) - farmer triggered it and manages
        # workers, but shouldn't get notified about their own action.
        self.assertFalse(low_stock_notifs.exists())
