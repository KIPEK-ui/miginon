"""Deterministic, rule-based farm advisories derived from a forecast payload.

Deliberately simple (no ML) and named "advisory" rather than "prediction" to
keep it distinct from analysis.ml.predict, which is a separate, unrelated
feature (per-cow/block milk yield forecasting)."""

from django.utils.translation import gettext as _

THUNDERSTORM_CODES = {95, 96, 99}
RAIN_CODES = {51, 53, 55, 61, 63, 65, 80, 81, 82}
CLEAR_CODES = {0, 1, 2}

HEAVY_RAIN_TOMORROW = 'heavy_rain_tomorrow'
THUNDERSTORM_AHEAD = 'thunderstorm_ahead'
HOT_DRY_SPELL = 'hot_dry_spell'
CLEAR_SPELL = 'clear_spell'
NORMAL = 'normal'


def build_advisory(forecast):
    """forecast: the raw Open-Meteo JSON payload (see weather.services.fetch_forecast).
    Returns (key, translated text) - the key is stored on WeatherCache so a
    cached forecast can still show the right text after a language switch."""
    daily = forecast.get('daily', {})
    codes = daily.get('weather_code', [])
    rain_probs = daily.get('precipitation_probability_max', [])
    highs = daily.get('temperature_2m_max', [])

    if len(rain_probs) > 1 and rain_probs[1] is not None and rain_probs[1] >= 50:
        return HEAVY_RAIN_TOMORROW, _(
            'Rain is likely tomorrow. Plan milking and outdoor feeding for the '
            'morning, and hold off on spraying or hay cutting until it clears.'
        )

    if any(code in THUNDERSTORM_CODES for code in codes[:3]):
        return THUNDERSTORM_AHEAD, _(
            'Thunderstorms are expected in the next few days. Make sure the herd '
            'has shelter and avoid fieldwork while storms are close.'
        )

    if highs[:3] and all(h is not None and h >= 32 for h in highs[:3]):
        return HOT_DRY_SPELL, _(
            'A hot spell is ahead. Check water troughs more often and make sure '
            'the herd has shade in the middle of the day.'
        )

    if codes[:3] and all(c in CLEAR_CODES for c in codes[:3]) and \
            all((p or 0) < 20 for p in rain_probs[:3]):
        return CLEAR_SPELL, _(
            'Clear skies for the next few days - a good window for haymaking, '
            'drying produce, or spraying.'
        )

    return NORMAL, _('Conditions look normal for the next few days.')
