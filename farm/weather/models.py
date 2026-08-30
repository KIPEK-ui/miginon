from django.db import models


class WeatherCache(models.Model):
    """One row per farm holding the most recently fetched Open-Meteo
    forecast. Refetched lazily (see weather.services.fetch_forecast) rather
    than on a schedule - a farm dashboard is checked a handful of times a
    day, so there's no need for a background job just to keep this warm."""

    farm = models.OneToOneField(
        'farms.Farm', on_delete=models.CASCADE, related_name='weather_cache'
    )
    fetched_at = models.DateTimeField(auto_now=True)
    payload = models.JSONField()
    advisory_key = models.CharField(max_length=40)

    def __str__(self):
        return f'Weather for {self.farm.name} @ {self.fetched_at:%Y-%m-%d %H:%M}'
