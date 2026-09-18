import datetime
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from cows.models import Cow, MilkRecord
from crops.models import Crop
from farms.models import Block, Farm, FarmMembership, FarmRole
from finance.models import Transaction
from inventory.models import InventoryItem
from tasks.models import Task

from .models import FarmInsight
from .services import MIN_MILK_ROWS, refresh_insights


class InsightsTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='farmer@example.com', first_name='Fay')
        self.farm = Farm.objects.create(name='Insight Farm', owner=self.user)
        FarmMembership.objects.create(user=self.user, farm=self.farm, role=FarmRole.FARMER)
        self.block = Block.objects.create(farm=self.farm, name='Block A')
        self.cow = Cow.objects.create(farm=self.farm, block=self.block, tag_id='C-001')

    def _log_milk(self, date, liters):
        MilkRecord.objects.create(farm=self.farm, cow=self.cow, block=self.block, date=date, session='AM', liters=liters)


class ColdStartTests(InsightsTestCase):
    def test_fires_below_threshold(self):
        refresh_insights(self.farm)
        self.assertTrue(FarmInsight.objects.filter(farm=self.farm, key='cold_start_milk').exists())

    def test_does_not_fire_once_enough_history(self):
        today = timezone.localdate()
        for i in range(MIN_MILK_ROWS):
            self._log_milk(today - datetime.timedelta(days=i), Decimal('10'))
        refresh_insights(self.farm)
        self.assertFalse(FarmInsight.objects.filter(farm=self.farm, key='cold_start_milk').exists())


class MilkTrendTests(InsightsTestCase):
    def _seed_history(self, last_week_daily, prior_week_daily):
        today = timezone.localdate()
        for i in range(7):
            self._log_milk(today - datetime.timedelta(days=i), last_week_daily)
        for i in range(7, 14):
            self._log_milk(today - datetime.timedelta(days=i), prior_week_daily)
        # pad past MIN_MILK_ROWS so the trend detector actually runs
        for i in range(14, MIN_MILK_ROWS + 14):
            self._log_milk(today - datetime.timedelta(days=i), prior_week_daily)

    def test_declining_yield_warns(self):
        self._seed_history(Decimal('5'), Decimal('10'))
        refresh_insights(self.farm)
        insight = FarmInsight.objects.get(farm=self.farm, key='milk_trend')
        self.assertEqual(insight.severity, FarmInsight.Severity.WARNING)

    def test_rising_yield_is_informational(self):
        self._seed_history(Decimal('15'), Decimal('10'))
        refresh_insights(self.farm)
        insight = FarmInsight.objects.get(farm=self.farm, key='milk_trend')
        self.assertEqual(insight.severity, FarmInsight.Severity.INFO)

    def test_stable_yield_produces_no_trend_insight(self):
        self._seed_history(Decimal('10'), Decimal('10'))
        refresh_insights(self.farm)
        self.assertFalse(FarmInsight.objects.filter(farm=self.farm, key='milk_trend').exists())

    def test_stale_trend_insight_is_removed_once_resolved(self):
        self._seed_history(Decimal('5'), Decimal('10'))
        refresh_insights(self.farm)
        self.assertTrue(FarmInsight.objects.filter(farm=self.farm, key='milk_trend').exists())

        MilkRecord.objects.filter(farm=self.farm).delete()
        self._seed_history(Decimal('10'), Decimal('10'))
        refresh_insights(self.farm)
        self.assertFalse(FarmInsight.objects.filter(farm=self.farm, key='milk_trend').exists())


class LowStockInsightTests(InsightsTestCase):
    def test_out_of_stock_is_critical(self):
        item = InventoryItem.objects.create(
            farm=self.farm, name='Dairy Meal', current_stock=Decimal('0'), reorder_level=Decimal('10'),
        )
        refresh_insights(self.farm)
        insight = FarmInsight.objects.get(farm=self.farm, key=f'low_stock_{item.id}')
        self.assertEqual(insight.severity, FarmInsight.Severity.CRITICAL)

    def test_below_reorder_but_positive_is_warning(self):
        item = InventoryItem.objects.create(
            farm=self.farm, name='Dairy Meal', current_stock=Decimal('5'), reorder_level=Decimal('10'),
        )
        refresh_insights(self.farm)
        insight = FarmInsight.objects.get(farm=self.farm, key=f'low_stock_{item.id}')
        self.assertEqual(insight.severity, FarmInsight.Severity.WARNING)

    def test_healthy_stock_produces_no_insight(self):
        item = InventoryItem.objects.create(
            farm=self.farm, name='Dairy Meal', current_stock=Decimal('50'), reorder_level=Decimal('10'),
        )
        refresh_insights(self.farm)
        self.assertFalse(FarmInsight.objects.filter(farm=self.farm, key=f'low_stock_{item.id}').exists())


class OverdueTaskInsightTests(InsightsTestCase):
    def test_overdue_task_fires(self):
        Task.objects.create(
            farm=self.farm, title='Deworm herd', due_date=timezone.localdate() - datetime.timedelta(days=3),
        )
        refresh_insights(self.farm)
        self.assertTrue(FarmInsight.objects.filter(farm=self.farm, key='overdue_tasks').exists())

    def test_future_task_does_not_fire(self):
        Task.objects.create(
            farm=self.farm, title='Deworm herd', due_date=timezone.localdate() + datetime.timedelta(days=3),
        )
        refresh_insights(self.farm)
        self.assertFalse(FarmInsight.objects.filter(farm=self.farm, key='overdue_tasks').exists())

    def test_done_task_does_not_count_as_overdue(self):
        task = Task.objects.create(
            farm=self.farm, title='Deworm herd', due_date=timezone.localdate() - datetime.timedelta(days=3),
        )
        task.mark_status(Task.Status.DONE)
        refresh_insights(self.farm)
        self.assertFalse(FarmInsight.objects.filter(farm=self.farm, key='overdue_tasks').exists())


class FinanceTrendInsightTests(InsightsTestCase):
    def _log(self, days_ago, kind, amount):
        Transaction.objects.create(
            farm=self.farm, kind=kind, amount=amount, date=timezone.localdate() - datetime.timedelta(days=days_ago),
        )

    def test_dropping_net_income_warns(self):
        self._log(5, Transaction.Kind.INCOME, Decimal('1000'))
        self._log(45, Transaction.Kind.INCOME, Decimal('10000'))
        refresh_insights(self.farm)
        self.assertTrue(FarmInsight.objects.filter(farm=self.farm, key='finance_trend').exists())

    def test_stable_income_does_not_warn(self):
        self._log(5, Transaction.Kind.INCOME, Decimal('1000'))
        self._log(45, Transaction.Kind.INCOME, Decimal('1000'))
        refresh_insights(self.farm)
        self.assertFalse(FarmInsight.objects.filter(farm=self.farm, key='finance_trend').exists())


class UpcomingHarvestInsightTests(InsightsTestCase):
    def test_harvest_within_a_week_fires(self):
        crop = Crop.objects.create(
            farm=self.farm, name='Maize', expected_harvest=timezone.localdate() + datetime.timedelta(days=3),
        )
        refresh_insights(self.farm)
        self.assertTrue(FarmInsight.objects.filter(farm=self.farm, key=f'harvest_{crop.id}').exists())

    def test_harvest_far_in_the_future_does_not_fire(self):
        crop = Crop.objects.create(
            farm=self.farm, name='Maize', expected_harvest=timezone.localdate() + datetime.timedelta(days=60),
        )
        refresh_insights(self.farm)
        self.assertFalse(FarmInsight.objects.filter(farm=self.farm, key=f'harvest_{crop.id}').exists())


class InsightsOverviewViewTests(InsightsTestCase):
    def test_view_renders_for_any_member(self):
        self.client.force_login(self.user)
        session = self.client.session
        session['active_farm_id'] = self.farm.id
        session.save()
        response = self.client.get('/insights/')
        self.assertEqual(response.status_code, 200)
