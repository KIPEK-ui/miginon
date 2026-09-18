from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase

from accounts.models import User
from farms.models import Farm, FarmMembership, FarmRole
from geomap.models import LandParcel
from inventory.models import InventoryItem

from .models import Crop, CropActivity

_SQUARE = [[36.80, -1.28], [36.801, -1.28], [36.801, -1.281], [36.80, -1.281]]


class CropsTestCase(TestCase):
    def setUp(self):
        self.farmer = User.objects.create_user(email='farmer@example.com', first_name='Fay')
        self.worker = User.objects.create_user(email='worker@example.com', first_name='Wes')
        self.farm = Farm.objects.create(name='Crop Farm', owner=self.farmer)
        FarmMembership.objects.create(user=self.farmer, farm=self.farm, role=FarmRole.FARMER)
        FarmMembership.objects.create(user=self.worker, farm=self.farm, role=FarmRole.WORKER)

    def _login(self, user):
        self.client.force_login(user)
        session = self.client.session
        session['active_farm_id'] = self.farm.id
        session.save()


class CropCreateViewTests(CropsTestCase):
    def test_farmer_can_add_a_crop(self):
        self._login(self.farmer)
        self.client.post('/crops/add/', {
            'name': 'Napier grass', 'field_name': 'North field', 'status': Crop.Status.PLANNED,
            'planted_on': '', 'expected_harvest': '',
        })
        crop = Crop.objects.get(farm=self.farm, name='Napier grass')
        self.assertEqual(crop.added_by, self.farmer)

    def test_worker_cannot_add_a_crop(self):
        self._login(self.worker)
        self.client.post('/crops/add/', {
            'name': 'Napier grass', 'field_name': '', 'status': Crop.Status.PLANNED,
            'planted_on': '', 'expected_harvest': '',
        })
        self.assertFalse(Crop.objects.filter(farm=self.farm).exists())


class CropLandParcelLinkTests(CropsTestCase):
    def test_crop_can_be_linked_to_own_farms_parcel(self):
        parcel = LandParcel.objects.create(
            farm=self.farm, name='North boundary', coordinates=_SQUARE,
            area_sqm=Decimal('10000.00'), perimeter_m=Decimal('400.00'),
        )
        self._login(self.farmer)
        self.client.post('/crops/add/', {
            'name': 'Maize', 'land_parcel': parcel.id, 'field_name': '', 'status': Crop.Status.PLANNED,
            'planted_on': '', 'expected_harvest': '',
        })
        crop = Crop.objects.get(farm=self.farm, name='Maize')
        self.assertEqual(crop.land_parcel, parcel)
        self.assertEqual(crop.field_label, 'North boundary')

    def test_cannot_link_to_another_farms_parcel(self):
        other_owner = User.objects.create_user(email='other@example.com', first_name='Otto')
        other_farm = Farm.objects.create(name='Other Farm', owner=other_owner)
        foreign_parcel = LandParcel.objects.create(
            farm=other_farm, name='Not yours', coordinates=_SQUARE,
            area_sqm=Decimal('10000.00'), perimeter_m=Decimal('400.00'),
        )
        self._login(self.farmer)
        response = self.client.post('/crops/add/', {
            'name': 'Maize', 'land_parcel': foreign_parcel.id, 'field_name': '', 'status': Crop.Status.PLANNED,
            'planted_on': '', 'expected_harvest': '',
        })
        self.assertFalse(Crop.objects.filter(farm=self.farm, name='Maize').exists())
        self.assertIn('land_parcel', response.context['form'].errors)

    def test_field_label_falls_back_to_free_text_field_name(self):
        crop = Crop.objects.create(farm=self.farm, name='Beans', field_name='South plot', added_by=self.farmer)
        self.assertEqual(crop.field_label, 'South plot')


class CropEditDeleteViewTests(CropsTestCase):
    def setUp(self):
        super().setUp()
        self.crop = Crop.objects.create(farm=self.farm, name='Maize', added_by=self.farmer)

    def test_worker_cannot_edit(self):
        self._login(self.worker)
        self.client.post(f'/crops/{self.crop.id}/edit/', {
            'name': 'Renamed', 'field_name': '', 'status': Crop.Status.PLANNED,
            'planted_on': '', 'expected_harvest': '',
        })
        self.crop.refresh_from_db()
        self.assertEqual(self.crop.name, 'Maize')

    def test_farmer_can_delete(self):
        self._login(self.farmer)
        self.client.post(f'/crops/{self.crop.id}/delete/')
        self.assertFalse(Crop.objects.filter(id=self.crop.id).exists())


class CropActivityViewTests(CropsTestCase):
    def setUp(self):
        super().setUp()
        self.crop = Crop.objects.create(farm=self.farm, name='Maize', added_by=self.farmer)

    def test_worker_can_log_a_non_harvest_activity(self):
        self._login(self.worker)
        self.client.post('/crops/activity/add/', {
            'crop': self.crop.id, 'date': '2026-01-05', 'activity_type': CropActivity.ActivityType.WEEDING,
            'quantity_harvested_kg': '', 'notes': '',
        })
        activity = CropActivity.objects.get(farm=self.farm, crop=self.crop)
        self.assertIsNone(activity.stock_movement)

    @patch('crops.views.mint_fiq', return_value=None)
    @patch('crops.views.mint_harvest_nft', return_value=None)
    def test_harvest_activity_restocks_produce_inventory(self, mock_mint_nft, mock_mint_fiq):
        self._login(self.worker)
        self.client.post('/crops/activity/add/', {
            'crop': self.crop.id, 'date': '2026-01-05', 'activity_type': CropActivity.ActivityType.HARVESTING,
            'quantity_harvested_kg': '120.00', 'notes': '',
        })
        activity = CropActivity.objects.get(farm=self.farm, crop=self.crop)
        self.assertIsNotNone(activity.stock_movement)
        item = InventoryItem.objects.get(farm=self.farm, name='Maize')
        self.assertEqual(item.category, InventoryItem.Category.PRODUCE)
        self.assertEqual(item.current_stock, Decimal('120.00'))
        mock_mint_nft.assert_called_once()

    @patch('crops.views.mint_fiq')
    @patch('crops.views.mint_harvest_nft')
    def test_harvest_certificate_minted_once_and_not_reminted_on_edit(self, mock_mint_nft, mock_mint_fiq):
        mock_mint_nft.return_value = {
            'token_id': '0.0.1', 'serial_number': 1, 'transaction_id': '0.0.1@123',
        }
        mock_mint_fiq.return_value = {'transaction_id': '0.0.2@123', 'amount_minted': Decimal('60.00')}
        self._login(self.farmer)
        self.client.post('/crops/activity/add/', {
            'crop': self.crop.id, 'date': '2026-01-05', 'activity_type': CropActivity.ActivityType.HARVESTING,
            'quantity_harvested_kg': '120.00', 'notes': '',
        })
        activity = CropActivity.objects.get(farm=self.farm, crop=self.crop)
        self.assertEqual(activity.hedera_token_id, '0.0.1')
        mock_mint_nft.assert_called_once()

        self.client.post(f'/crops/activity/{activity.id}/edit/', {
            'crop': self.crop.id, 'date': '2026-01-05', 'activity_type': CropActivity.ActivityType.HARVESTING,
            'quantity_harvested_kg': '150.00', 'notes': 'updated',
        })
        # Editing re-syncs the stock movement to the new quantity, but the
        # certificate is never re-minted once hedera_token_id is set (see
        # crops.views._sync_harvest_certificate's idempotency guard).
        mock_mint_nft.assert_called_once()
        item = InventoryItem.objects.get(farm=self.farm, name='Maize')
        self.assertEqual(item.current_stock, Decimal('150.00'))

    def test_deleting_a_harvest_activity_reverses_stock(self):
        with patch('crops.views.mint_fiq', return_value=None), patch('crops.views.mint_harvest_nft', return_value=None):
            self._login(self.farmer)
            self.client.post('/crops/activity/add/', {
                'crop': self.crop.id, 'date': '2026-01-05', 'activity_type': CropActivity.ActivityType.HARVESTING,
                'quantity_harvested_kg': '50.00', 'notes': '',
            })
        activity = CropActivity.objects.get(farm=self.farm, crop=self.crop)
        self.client.post(f'/crops/activity/{activity.id}/delete/')
        item = InventoryItem.objects.get(farm=self.farm, name='Maize')
        self.assertEqual(item.current_stock, Decimal('0.00'))


class CropRecommendationTests(CropsTestCase):
    def test_crop_list_shows_recommendations_for_the_farms_county(self):
        self.farm.county = 'Kiambu'
        self.farm.save(update_fields=['county'])
        self._login(self.farmer)
        response = self.client.get('/crops/')
        crop_names = [c.crop_name for c in response.context['recommended_crops']]
        self.assertIn('Tea', crop_names)

    def test_crop_list_has_no_recommendations_without_a_county(self):
        self._login(self.farmer)
        response = self.client.get('/crops/')
        self.assertEqual(response.context['recommended_crops'], [])

    def test_crop_create_prefills_name_from_query_param(self):
        self._login(self.farmer)
        response = self.client.get('/crops/add/?name=Tea')
        self.assertEqual(response.context['form'].initial['name'], 'Tea')
