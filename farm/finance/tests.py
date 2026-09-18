from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase

from accounts.models import User
from farms.models import Farm, FarmMembership, FarmRole
from inventory.models import InventoryItem

from .models import Transaction


class FinanceTestCase(TestCase):
    def setUp(self):
        self.farmer = User.objects.create_user(email='farmer@example.com', first_name='Fay')
        self.worker = User.objects.create_user(email='worker@example.com', first_name='Wes')
        self.farm = Farm.objects.create(name='Money Farm', owner=self.farmer)
        FarmMembership.objects.create(user=self.farmer, farm=self.farm, role=FarmRole.FARMER)
        FarmMembership.objects.create(user=self.worker, farm=self.farm, role=FarmRole.WORKER)

    def _login(self, user):
        self.client.force_login(user)
        session = self.client.session
        session['active_farm_id'] = self.farm.id
        session.save()


class TransactionCreateViewTests(FinanceTestCase):
    @patch('finance.services.anchor_hash')
    def test_farmer_can_record_a_transaction(self, mock_anchor):
        mock_anchor.return_value = None
        self._login(self.farmer)
        response = self.client.post('/finance/add/', {
            'kind': Transaction.Kind.EXPENSE, 'category': Transaction.Category.FEED,
            'amount': '1500.00', 'date': '2026-01-05', 'note': 'Dairy meal restock',
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        transaction = Transaction.objects.get(farm=self.farm)
        self.assertEqual(transaction.kind, Transaction.Kind.EXPENSE)
        self.assertEqual(transaction.amount, Decimal('1500.00'))
        self.assertEqual(transaction.recorded_by, self.farmer)
        mock_anchor.assert_called_once()

    @patch('finance.services.anchor_hash')
    def test_worker_can_also_record_a_transaction(self, mock_anchor):
        # log_activity_required == record_production_required: every role,
        # including Worker, can log day-to-day activity - only editing/
        # deleting an existing record is restricted (see edit/delete tests).
        mock_anchor.return_value = None
        self._login(self.worker)
        self.client.post('/finance/add/', {
            'kind': Transaction.Kind.INCOME, 'category': Transaction.Category.SALES,
            'amount': '300.00', 'date': '2026-01-05', 'note': '',
        })
        self.assertEqual(Transaction.objects.filter(farm=self.farm).count(), 1)

    @patch('finance.services.anchor_hash')
    def test_content_hash_populated_when_anchoring_succeeds(self, mock_anchor):
        mock_anchor.return_value = {
            'topic_id': '0.0.111', 'sequence_number': 1, 'consensus_timestamp': '123.456',
        }
        self._login(self.farmer)
        self.client.post('/finance/add/', {
            'kind': Transaction.Kind.EXPENSE, 'category': Transaction.Category.OTHER,
            'amount': '50.00', 'date': '2026-01-05', 'note': '',
        })
        transaction = Transaction.objects.get(farm=self.farm)
        self.assertTrue(transaction.content_hash)
        self.assertEqual(transaction.hedera_topic_id, '0.0.111')

    @patch('finance.services.anchor_hash')
    def test_anchor_failure_does_not_block_the_transaction(self, mock_anchor):
        mock_anchor.return_value = None
        self._login(self.farmer)
        self.client.post('/finance/add/', {
            'kind': Transaction.Kind.EXPENSE, 'category': Transaction.Category.OTHER,
            'amount': '50.00', 'date': '2026-01-05', 'note': '',
        })
        transaction = Transaction.objects.get(farm=self.farm)
        self.assertEqual(transaction.content_hash, '')


class TransactionEditDeleteViewTests(FinanceTestCase):
    def setUp(self):
        super().setUp()
        with patch('finance.services.anchor_hash', return_value=None):
            self.transaction = Transaction.objects.create(
                farm=self.farm, kind=Transaction.Kind.EXPENSE, category=Transaction.Category.OTHER,
                amount=Decimal('20.00'), date='2026-01-01', recorded_by=self.farmer,
            )

    def test_farmer_can_edit(self):
        self._login(self.farmer)
        response = self.client.post(f'/finance/{self.transaction.id}/edit/', {
            'kind': Transaction.Kind.EXPENSE, 'category': Transaction.Category.OTHER,
            'amount': '99.00', 'date': '2026-01-01', 'note': 'corrected',
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        self.transaction.refresh_from_db()
        self.assertEqual(self.transaction.amount, Decimal('99.00'))

    def test_worker_cannot_edit(self):
        self._login(self.worker)
        self.client.post(f'/finance/{self.transaction.id}/edit/', {
            'kind': Transaction.Kind.EXPENSE, 'category': Transaction.Category.OTHER,
            'amount': '99.00', 'date': '2026-01-01', 'note': 'should not apply',
        })
        self.transaction.refresh_from_db()
        self.assertEqual(self.transaction.amount, Decimal('20.00'))

    def test_worker_cannot_delete(self):
        self._login(self.worker)
        self.client.post(f'/finance/{self.transaction.id}/delete/')
        self.assertTrue(Transaction.objects.filter(id=self.transaction.id).exists())

    def test_farmer_can_delete(self):
        self._login(self.farmer)
        self.client.post(f'/finance/{self.transaction.id}/delete/')
        self.assertFalse(Transaction.objects.filter(id=self.transaction.id).exists())


class MilkSaleCreateViewTests(FinanceTestCase):
    @patch('finance.services.anchor_hash', return_value=None)
    def test_milk_sale_creates_transaction_and_draws_down_stock(self, mock_anchor):
        InventoryItem.objects.create(
            farm=self.farm, name='Milk', category=InventoryItem.Category.PRODUCE,
            unit=InventoryItem.Unit.LITRES, current_stock=Decimal('100.00'),
        )
        self._login(self.farmer)
        response = self.client.post('/finance/milk-sale/', {
            'date': '2026-01-05', 'liters': '40', 'amount': '2000.00', 'note': 'Local buyer',
        }, follow=True)
        self.assertEqual(response.status_code, 200)

        transaction = Transaction.objects.get(farm=self.farm, category=Transaction.Category.SALES)
        self.assertEqual(transaction.kind, Transaction.Kind.INCOME)
        self.assertEqual(transaction.amount, Decimal('2000.00'))

        milk_item = InventoryItem.objects.get(farm=self.farm, name='Milk')
        self.assertEqual(milk_item.current_stock, Decimal('60.00'))

    @patch('finance.services.anchor_hash', return_value=None)
    def test_selling_more_than_in_stock_warns_but_still_records(self, mock_anchor):
        InventoryItem.objects.create(
            farm=self.farm, name='Milk', category=InventoryItem.Category.PRODUCE,
            unit=InventoryItem.Unit.LITRES, current_stock=Decimal('5.00'),
        )
        self._login(self.farmer)
        response = self.client.post('/finance/milk-sale/', {
            'date': '2026-01-05', 'liters': '10', 'amount': '500.00', 'note': '',
        }, follow=True)
        messages = [str(m) for m in response.context['messages']]
        self.assertTrue(any('negative' in m for m in messages))
        milk_item = InventoryItem.objects.get(farm=self.farm, name='Milk')
        self.assertEqual(milk_item.current_stock, Decimal('-5.00'))
