import json

from django.test import TestCase

from accounts.models import User
from farms.models import Farm, FarmMembership, FarmRole

from .models import LandParcel
from .services import area_sqm, perimeter_m

# Roughly a 100m x 100m square near the equator, where 1 degree of
# longitude and latitude are both close to 111,320m - used to sanity-check
# the geodesic area/perimeter formulas against an easy expected value.
_SQUARE_100M = [
    [36.8000, -1.2800],
    [36.8009, -1.2800],
    [36.8009, -1.2791],
    [36.8000, -1.2791],
]


class GeodesyServiceTests(TestCase):
    def test_area_of_roughly_square_hectare(self):
        area = area_sqm(_SQUARE_100M)
        self.assertAlmostEqual(area, 10000, delta=200)

    def test_perimeter_of_roughly_square_hectare(self):
        perimeter = perimeter_m(_SQUARE_100M)
        self.assertAlmostEqual(perimeter, 400, delta=10)

    def test_area_of_line_is_zero(self):
        self.assertEqual(area_sqm(_SQUARE_100M[:2]), 0.0)


class ParcelMapViewTests(TestCase):
    def setUp(self):
        self.farmer = User.objects.create_user(email='farmer@example.com', first_name='Fay')
        self.worker = User.objects.create_user(email='worker@example.com', first_name='Wes')
        self.farm = Farm.objects.create(name='Geo Farm', owner=self.farmer, latitude=-1.28, longitude=36.80)
        FarmMembership.objects.create(user=self.farmer, farm=self.farm, role=FarmRole.FARMER)
        FarmMembership.objects.create(user=self.worker, farm=self.farm, role=FarmRole.WORKER)

    def _login(self, user):
        self.client.force_login(user)
        session = self.client.session
        session['active_farm_id'] = self.farm.id
        session.save()

    def test_map_page_loads_for_any_member(self):
        self._login(self.worker)
        response = self.client.get('/geomap/')
        self.assertEqual(response.status_code, 200)

    def test_farmer_can_save_a_parcel(self):
        self._login(self.farmer)
        response = self.client.post('/geomap/save/', {
            'name': 'North boundary',
            'block': '',
            'coordinates_json': json.dumps(_SQUARE_100M),
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        parcel = LandParcel.objects.get(farm=self.farm)
        self.assertEqual(parcel.name, 'North boundary')
        self.assertEqual(parcel.created_by, self.farmer)
        self.assertAlmostEqual(float(parcel.area_sqm), 10000, delta=200)

    def test_worker_cannot_save_a_parcel(self):
        self._login(self.worker)
        response = self.client.post('/geomap/save/', {
            'name': 'Should be blocked',
            'block': '',
            'coordinates_json': json.dumps(_SQUARE_100M),
        })
        self.assertEqual(LandParcel.objects.count(), 0)
        self.assertNotEqual(response.status_code, 200)

    def test_fewer_than_three_points_is_rejected(self):
        self._login(self.farmer)
        self.client.post('/geomap/save/', {
            'name': 'Too few points',
            'block': '',
            'coordinates_json': json.dumps(_SQUARE_100M[:2]),
        })
        self.assertEqual(LandParcel.objects.count(), 0)

    def test_farmer_can_delete_a_parcel(self):
        parcel = LandParcel.objects.create(
            farm=self.farm, name='To delete', coordinates=_SQUARE_100M,
            area_sqm=10000, perimeter_m=400, created_by=self.farmer,
        )
        self._login(self.farmer)
        self.client.post(f'/geomap/{parcel.id}/delete/')
        self.assertFalse(LandParcel.objects.filter(id=parcel.id).exists())
