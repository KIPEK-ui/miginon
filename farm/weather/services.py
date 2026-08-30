import logging
from datetime import date as date_cls

import requests
from django.utils import timezone
from django.utils.translation import gettext as _

from .models import WeatherCache

logger = logging.getLogger(__name__)

FORECAST_URL = 'https://api.open-meteo.com/v1/forecast'
CACHE_TTL_MINUTES = 60

# WMO weather codes (the set Open-Meteo returns) collapsed down to the handful
# of conditions worth showing on a farm dashboard, each mapped to the ionicon
# name templates use directly: <ion-icon name="{{ day.icon }}">, matching how
# every other icon in this app is rendered (see templates/app_base.html).
_CODE_TABLE = {
    0: ('sunny-outline', _('Clear sky')),
    1: ('partly-sunny-outline', _('Mostly clear')),
    2: ('partly-sunny-outline', _('Partly cloudy')),
    3: ('cloud-outline', _('Overcast')),
    45: ('cloud-outline', _('Foggy')),
    48: ('cloud-outline', _('Foggy')),
    51: ('rainy-outline', _('Light drizzle')),
    53: ('rainy-outline', _('Drizzle')),
    55: ('rainy-outline', _('Dense drizzle')),
    61: ('rainy-outline', _('Light rain')),
    63: ('rainy-outline', _('Rain')),
    65: ('rainy-outline', _('Heavy rain')),
    80: ('rainy-outline', _('Rain showers')),
    81: ('rainy-outline', _('Rain showers')),
    82: ('rainy-outline', _('Violent rain showers')),
    95: ('thunderstorm-outline', _('Thunderstorm')),
    96: ('thunderstorm-outline', _('Thunderstorm with hail')),
    99: ('thunderstorm-outline', _('Thunderstorm with hail')),
}
_DEFAULT_CONDITION = ('cloud-outline', _('Overcast'))


def describe_code(code):
    """WMO weather code -> (ionicon name, translated condition text)."""
    return _CODE_TABLE.get(code, _DEFAULT_CONDITION)


def _cache_is_fresh(cache):
    age = timezone.now() - cache.fetched_at
    return age.total_seconds() < CACHE_TTL_MINUTES * 60


def fetch_forecast(farm, force=False):
    """Return the cached/fresh forecast payload for a farm, or None if the
    farm has no coordinates yet or Open-Meteo can't be reached. Never
    raises - weather is a nice-to-have on the dashboard, not something that
    should be able to break it."""
    cache = WeatherCache.objects.filter(farm=farm).first()
    if cache and not force and _cache_is_fresh(cache):
        return cache.payload

    if farm.latitude is None or farm.longitude is None:
        return cache.payload if cache else None

    try:
        response = requests.get(
            FORECAST_URL,
            params={
                'latitude': str(farm.latitude),
                'longitude': str(farm.longitude),
                'current': 'temperature_2m,weather_code',
                'daily': 'weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max',
                'timezone': 'Africa/Nairobi',
                'forecast_days': 5,
            },
            timeout=6,
        )
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError):
        logger.exception('Failed to fetch weather forecast for farm %s', farm.id)
        return cache.payload if cache else None

    from .advisory import build_advisory  # local import: advisory needs describe_code, avoid a cycle

    advisory_key, _advisory_text = build_advisory(data)
    WeatherCache.objects.update_or_create(
        farm=farm, defaults={'payload': data, 'advisory_key': advisory_key}
    )
    return data


def get_forecast_summary(farm, force=False):
    """The fully-shaped forecast used by the Weather page, the Home
    dashboard's Weather card, and the Analysis overview: current
    conditions, a 5-day list, the field advisory text, and when it was
    fetched - or None if there's nothing to show yet (no coordinates, or
    Open-Meteo unreachable). `force` bypasses the cache TTL (see the
    Weather page's Refresh action)."""
    from .advisory import build_advisory  # local import: avoid a cycle with advisory's own imports

    data = fetch_forecast(farm, force=force)
    if not data:
        return None

    current = data.get('current', {})
    daily = data.get('daily', {})
    codes = daily.get('weather_code', [])
    highs = daily.get('temperature_2m_max', [])
    lows = daily.get('temperature_2m_min', [])
    rain_probs = daily.get('precipitation_probability_max', [])
    current_icon, current_condition = describe_code(current.get('weather_code'))
    _key, advisory_text = build_advisory(data)

    days = []
    for i, iso_date in enumerate(daily.get('time', [])):
        icon, condition = describe_code(codes[i] if i < len(codes) else None)
        days.append({
            # Open-Meteo returns plain "YYYY-MM-DD" strings - parsed into a
            # real date here so {{ day.date|date:"..." }} works in templates
            # instead of silently no-op'ing on a string.
            'date': date_cls.fromisoformat(iso_date),
            'icon': icon,
            'condition': condition,
            'high': highs[i] if i < len(highs) else None,
            'low': lows[i] if i < len(lows) else None,
            'rain_probability': rain_probs[i] if i < len(rain_probs) else None,
        })

    fetched_at = WeatherCache.objects.filter(farm=farm).values_list('fetched_at', flat=True).first()

    return {
        'current_temp': current.get('temperature_2m'),
        'current_icon': current_icon,
        'current_condition': current_condition,
        'days': days,
        'advisory': advisory_text,
        'fetched_at': fetched_at,
    }
