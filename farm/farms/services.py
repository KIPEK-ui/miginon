import logging

import requests
from django.urls import reverse
from django.utils.translation import gettext as _

from core.email import send_styled_email_safely

logger = logging.getLogger(__name__)

GEOCODING_URL = 'https://geocoding-api.open-meteo.com/v1/search'


def geocode_farm_location(farm):
    """Resolve farm.county/location (free-text town names) to a lat/lon via
    Open-Meteo's free geocoding API, and save it on the farm. Called once at
    farm creation and again whenever the location changes (see
    accounts.views.signup_otp, farms.views.add_farm/farm_settings).

    Best-effort only: geocoding is what powers the weather feature, not
    anything the signup/settings flow itself depends on, so any failure is
    logged and swallowed rather than raised - a farm with no coordinates
    just shows "weather unavailable" instead of breaking signup."""
    if not farm.location:
        return
    try:
        response = requests.get(
            GEOCODING_URL,
            params={'name': farm.location, 'count': 1, 'language': 'en', 'country': 'KE'},
            timeout=6,
        )
        response.raise_for_status()
        results = response.json().get('results') or []
    except (requests.RequestException, ValueError):
        logger.exception('Failed to geocode location %r for farm %s', farm.location, farm.id)
        return
    if not results:
        return
    farm.latitude = results[0]['latitude']
    farm.longitude = results[0]['longitude']
    farm.save(update_fields=['latitude', 'longitude'])


def send_worker_added_email(membership, request):
    farm = membership.farm
    send_styled_email_safely(
        to=membership.user.email,
        subject=_('You were added to %(farm)s on FarmIQ') % {'farm': farm.name},
        template_name='emails/worker_added.html',
        context={
            'membership': membership, 'farm': farm,
            'login_url': request.build_absolute_uri(reverse('accounts:login_farm')),
        },
    )
