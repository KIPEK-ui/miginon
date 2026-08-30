from datetime import date
from unittest.mock import Mock, patch

from django.test import TestCase

from accounts.models import User
from farms.models import Farm

from .exporters import build_pdf_bytes, export_csv, export_xlsx
from .reports import build_report

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


class ReportWeatherTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='report@example.com', first_name='Rep')
        self.farm = Farm.objects.create(name='Report Farm', owner=self.user, county='Uasin Gishu', location='Eldoret')
        self.start = date(2026, 8, 1)
        self.end = date(2026, 8, 31)

    def test_report_has_no_weather_without_coordinates(self):
        report = build_report(self.farm, self.start, self.end, 'August 2026')
        self.assertIsNone(report['weather'])

    def test_exporters_do_not_crash_without_weather(self):
        report = build_report(self.farm, self.start, self.end, 'August 2026')
        self.assertEqual(export_csv(report).status_code, 200)
        self.assertEqual(export_xlsx(report).status_code, 200)
        self.assertTrue(build_pdf_bytes(report).startswith(b'%PDF'))

    @patch('weather.services.requests.get')
    def test_report_includes_weather_when_available(self, mock_get):
        self.farm.latitude = 0.52
        self.farm.longitude = 35.27
        self.farm.save(update_fields=['latitude', 'longitude'])
        mock_get.return_value = Mock(status_code=200, json=lambda: _OPEN_METEO_PAYLOAD)
        mock_get.return_value.raise_for_status = lambda: None

        report = build_report(self.farm, self.start, self.end, 'August 2026')
        self.assertIsNotNone(report['weather'])
        self.assertEqual(len(report['weather']['days']), 5)

        self.assertEqual(export_csv(report).status_code, 200)
        self.assertEqual(export_xlsx(report).status_code, 200)
        self.assertTrue(build_pdf_bytes(report).startswith(b'%PDF'))
