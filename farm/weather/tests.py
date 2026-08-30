from datetime import date
from unittest.mock import Mock, patch

from django.test import TestCase

from .advisory import (
    CLEAR_SPELL,
    HEAVY_RAIN_TOMORROW,
    HOT_DRY_SPELL,
    NORMAL,
    THUNDERSTORM_AHEAD,
    build_advisory,
)

_OPEN_METEO_PAYLOAD = {
    'current': {'temperature_2m': 24.5, 'weather_code': 3},
    'daily': {
        'time': ['2026-08-30', '2026-08-31', '2026-09-01', '2026-09-02', '2026-09-03'],
        'weather_code': [3, 1, 61, 0, 2],
        'temperature_2m_max': [26, 27, 24, 28, 25],
        'temperature_2m_min': [14, 15, 13, 16, 14],
        'precipitation_probability_max': [10, 5, 60, 0, 20],
    },
}


def _forecast(codes, highs=None, rain_probs=None):
    return {
        'daily': {
            'weather_code': codes,
            'temperature_2m_max': highs or [25] * len(codes),
            'precipitation_probability_max': rain_probs or [10] * len(codes),
        }
    }


class AdvisoryTests(TestCase):
    def test_heavy_rain_tomorrow_takes_priority(self):
        forecast = _forecast([0, 61, 0, 0, 0], rain_probs=[10, 65, 10, 10, 10])
        key, text = build_advisory(forecast)
        self.assertEqual(key, HEAVY_RAIN_TOMORROW)
        self.assertIn('Rain is likely tomorrow', text)

    def test_thunderstorm_ahead(self):
        forecast = _forecast([0, 0, 95], rain_probs=[10, 10, 10])
        key, text = build_advisory(forecast)
        self.assertEqual(key, THUNDERSTORM_AHEAD)
        self.assertIn('Thunderstorms', text)

    def test_hot_dry_spell(self):
        forecast = _forecast([0, 0, 0], highs=[33, 34, 32], rain_probs=[5, 5, 5])
        key, text = build_advisory(forecast)
        self.assertEqual(key, HOT_DRY_SPELL)
        self.assertIn('hot spell', text)

    def test_clear_spell(self):
        forecast = _forecast([0, 1, 2], rain_probs=[5, 10, 15])
        key, text = build_advisory(forecast)
        self.assertEqual(key, CLEAR_SPELL)
        self.assertIn('Clear skies', text)

    def test_normal_default(self):
        forecast = _forecast([3, 3, 3], rain_probs=[30, 30, 30])
        key, text = build_advisory(forecast)
        self.assertEqual(key, NORMAL)


class GeocodeFarmLocationTests(TestCase):
    def setUp(self):
        from accounts.models import User
        from farms.models import Farm
        self.user = User.objects.create_user(email='geo@example.com', first_name='Geo')
        self.farm = Farm.objects.create(name='Geo Farm', owner=self.user, county='Uasin Gishu', location='Eldoret')

    @patch('farms.services.requests.get')
    def test_geocode_saves_coordinates(self, mock_get):
        mock_get.return_value = Mock(
            status_code=200,
            json=lambda: {'results': [{'latitude': 0.52, 'longitude': 35.27}]},
        )
        mock_get.return_value.raise_for_status = lambda: None
        from farms.services import geocode_farm_location
        geocode_farm_location(self.farm)
        self.farm.refresh_from_db()
        self.assertEqual(float(self.farm.latitude), 0.52)
        self.assertEqual(float(self.farm.longitude), 35.27)

    @patch('farms.services.requests.get')
    def test_geocode_failure_is_swallowed(self, mock_get):
        import requests
        mock_get.side_effect = requests.RequestException('network down')
        from farms.services import geocode_farm_location
        geocode_farm_location(self.farm)  # must not raise
        self.farm.refresh_from_db()
        self.assertIsNone(self.farm.latitude)

    @patch('farms.services.requests.get')
    def test_geocode_no_results_leaves_coordinates_unset(self, mock_get):
        mock_get.return_value = Mock(status_code=200, json=lambda: {'results': []})
        mock_get.return_value.raise_for_status = lambda: None
        from farms.services import geocode_farm_location
        geocode_farm_location(self.farm)
        self.farm.refresh_from_db()
        self.assertIsNone(self.farm.latitude)


class GetForecastSummaryTests(TestCase):
    def setUp(self):
        from accounts.models import User
        from farms.models import Farm
        self.user = User.objects.create_user(email='fc@example.com', first_name='Fc')
        self.farm = Farm.objects.create(
            name='Forecast Farm', owner=self.user, county='Uasin Gishu', location='Eldoret',
            latitude=0.52, longitude=35.27,
        )

    @patch('weather.services.requests.get')
    def test_day_dates_are_real_date_objects(self, mock_get):
        mock_get.return_value = Mock(status_code=200, json=lambda: _OPEN_METEO_PAYLOAD)
        mock_get.return_value.raise_for_status = lambda: None
        from weather.services import get_forecast_summary
        summary = get_forecast_summary(self.farm)
        self.assertEqual(len(summary['days']), 5)
        self.assertEqual(summary['days'][0]['date'], date(2026, 8, 30))
        self.assertIsInstance(summary['days'][0]['date'], date)

    @patch('weather.services.requests.get')
    def test_fetched_at_is_populated(self, mock_get):
        mock_get.return_value = Mock(status_code=200, json=lambda: _OPEN_METEO_PAYLOAD)
        mock_get.return_value.raise_for_status = lambda: None
        from weather.services import get_forecast_summary
        summary = get_forecast_summary(self.farm)
        self.assertIsNotNone(summary['fetched_at'])

    def test_no_coordinates_returns_none(self):
        self.farm.latitude = None
        self.farm.longitude = None
        self.farm.save(update_fields=['latitude', 'longitude'])
        from weather.services import get_forecast_summary
        self.assertIsNone(get_forecast_summary(self.farm))


class RefreshViewTests(TestCase):
    def setUp(self):
        from accounts.models import User
        from farms.models import Farm, FarmMembership
        self.user = User.objects.create_user(email='refresh@example.com', first_name='Ref')
        self.farm = Farm.objects.create(
            name='Refresh Farm', owner=self.user, county='Uasin Gishu', location='Eldoret',
            latitude=0.52, longitude=35.27,
        )
        FarmMembership.objects.create(user=self.user, farm=self.farm, role='farmer', status=FarmMembership.Status.ACTIVE)
        self.client.force_login(self.user)
        session = self.client.session
        session['active_farm_id'] = self.farm.id
        session.save()

    def test_get_does_not_trigger_refresh(self):
        response = self.client.get('/weather/refresh/')
        self.assertRedirects(response, '/weather/')

    @patch('weather.services.requests.get')
    def test_post_forces_a_fresh_fetch(self, mock_get):
        mock_get.return_value = Mock(status_code=200, json=lambda: _OPEN_METEO_PAYLOAD)
        mock_get.return_value.raise_for_status = lambda: None
        response = self.client.post('/weather/refresh/')
        self.assertRedirects(response, '/weather/')
        self.assertTrue(mock_get.called)

    def test_refresh_without_coordinates_shows_error_not_crash(self):
        self.farm.latitude = None
        self.farm.longitude = None
        self.farm.save(update_fields=['latitude', 'longitude'])
        response = self.client.post('/weather/refresh/', follow=True)
        self.assertEqual(response.status_code, 200)
