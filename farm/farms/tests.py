from datetime import date

from django.test import TestCase

from accounts.models import User
from advisory.models import DiseaseCatalog, Guide
from cows.models import Cow, FeedingRecord, MilkRecord
from crops.models import Crop, CropActivity
from finance.models import Transaction
from inventory.models import InventoryItem, StockMovement
from notifications.models import Notification
from tasks.models import Task

from .models import Block, Farm, FarmMembership, FarmRole


class FullSiteCrawlTests(TestCase):
    """A broad, read-only smoke test: seed one of everything and GET every
    list/detail/create-form page for both a Farmer and a Worker. This is the
    kind of check that catches a template error only a *populated* page
    would hit (an empty-state {% empty %} branch renders fine either way) -
    exactly the risk the sitewide dark-mode/i18n sweep carried across ~68
    templates. Not a replacement for the app-specific unit tests elsewhere,
    just a wide, shallow safety net."""

    def setUp(self):
        self.owner = User.objects.create_user(email='crawl-owner@example.com', first_name='Owner')
        self.worker = User.objects.create_user(email='crawl-worker@example.com', first_name='Worker')
        self.farm = Farm.objects.create(name='Crawl Farm', owner=self.owner, county='Uasin Gishu', location='Eldoret')
        self.owner_membership = FarmMembership.objects.create(
            user=self.owner, farm=self.farm, role=FarmRole.FARMER, status=FarmMembership.Status.ACTIVE
        )
        self.worker_membership = FarmMembership.objects.create(
            user=self.worker, farm=self.farm, role=FarmRole.WORKER, status=FarmMembership.Status.ACTIVE
        )

        self.block = Block.objects.create(farm=self.farm, name='Block A', created_by=self.owner)
        self.cow = Cow.objects.create(farm=self.farm, block=self.block, tag_id='C-001', added_by=self.owner)
        self.milk = MilkRecord.objects.create(
            farm=self.farm, cow=self.cow, block=self.block, date=date.today(), session='AM', liters=12, recorded_by=self.owner,
        )
        self.feeding = FeedingRecord.objects.create(
            farm=self.farm, block=self.block, date=date.today(), session='AM',
            dairy_meal_kg=5, silage_hay_kg=10, recorded_by=self.owner,
        )
        self.crop = Crop.objects.create(farm=self.farm, name='Napier grass', added_by=self.owner)
        self.activity = CropActivity.objects.create(
            farm=self.farm, crop=self.crop, date=date.today(), activity_type='planting', recorded_by=self.owner,
        )
        self.item = InventoryItem.objects.create(farm=self.farm, name='Dairy meal', added_by=self.owner)
        self.movement = StockMovement.objects.create(
            farm=self.farm, item=self.item, date=date.today(), movement_type='restock',
            quantity=50, stock_before=0, recorded_by=self.owner,
        )
        self.transaction = Transaction.objects.create(
            farm=self.farm, kind='income', category='produce_sales', amount=1000, date=date.today(), recorded_by=self.owner,
        )
        self.task = Task.objects.create(farm=self.farm, title='Feed Block A', assigned_to=self.worker_membership, created_by=self.owner)
        Notification.objects.create(
            farm=self.farm, actor=self.owner, verb=Notification.Verb.CREATED, kind='cow', description=str(self.cow),
        )

    def _login_as(self, user):
        client = self.client_class()
        client.force_login(user)
        session = client.session
        session['active_farm_id'] = self.farm.id
        session.save()
        return client

    def _urls_for(self, role_is_owner):
        dairy_disease = DiseaseCatalog.objects.filter(category='dairy').first()
        crop_disease = DiseaseCatalog.objects.filter(category='crop').first()
        guide = Guide.objects.first()
        urls = [
            '/farm/', '/weather/', '/farm/map/', '/farm/blocks/', f'/farm/blocks/{self.block.id}/',
            '/cows/', f'/cows/{self.cow.id}/', '/cows/feeding/', '/cows/milk/',
            '/crops/', f'/crops/{self.crop.id}/', '/crops/activity/',
            '/inventory/', f'/inventory/{self.item.id}/', '/inventory/movements/',
            '/finance/',
            '/tasks/', f'/tasks/{self.task.id}/',
            '/notifications/',
            '/accounts/settings/',
            '/advisory/', '/advisory/diseases/', '/advisory/guides/', '/advisory/agri-centers/',
        ]
        if dairy_disease:
            urls.append(f'/advisory/diseases/{dairy_disease.id}/')
        if crop_disease:
            urls.append(f'/advisory/diseases/{crop_disease.id}/')
        if guide:
            urls.append(f'/advisory/guides/{guide.id}/')
        if role_is_owner:
            urls += ['/analysis/', '/analysis/predictions/', '/farm/workers/', '/farm/settings/']
        return urls

    def test_owner_can_reach_every_page(self):
        client = self._login_as(self.owner)
        for url in self._urls_for(role_is_owner=True):
            with self.subTest(url=url):
                response = client.get(url)
                self.assertEqual(response.status_code, 200, f'{url} returned {response.status_code}')

    def test_worker_can_reach_every_page_they_have_access_to(self):
        client = self._login_as(self.worker)
        for url in self._urls_for(role_is_owner=False):
            with self.subTest(url=url):
                response = client.get(url)
                self.assertEqual(response.status_code, 200, f'{url} returned {response.status_code}')

    def test_owner_can_reach_every_create_form(self):
        client = self._login_as(self.owner)
        for url in [
            '/cows/add/', '/cows/feeding/add/', '/cows/milk/add/',
            '/crops/add/', '/crops/activity/add/',
            '/inventory/add/', '/inventory/movements/add/', '/inventory/milk-usage/',
            '/finance/add/', '/finance/milk-sale/',
            '/tasks/add/', '/farm/workers/invite/', '/farm/blocks/add/',
        ]:
            with self.subTest(url=url):
                response = client.get(url)
                self.assertEqual(response.status_code, 200, f'{url} returned {response.status_code}')

    def test_dark_mode_and_kiswahili_render_cleanly(self):
        self.owner.theme_preference = User.ThemePreference.DARK
        self.owner.language = User.Language.KISWAHILI
        self.owner.save(update_fields=['theme_preference', 'language'])
        client = self._login_as(self.owner)
        for url in ['/farm/', '/cows/', f'/cows/{self.cow.id}/', '/crops/', '/inventory/', '/finance/', '/tasks/', '/analysis/', '/weather/']:
            with self.subTest(url=url):
                response = client.get(url)
                self.assertEqual(response.status_code, 200, f'{url} returned {response.status_code}')
