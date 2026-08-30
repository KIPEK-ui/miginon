from math import asin, cos, radians, sin, sqrt

from .models import AgriCenter

EARTH_RADIUS_KM = 6371


def _haversine_km(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * asin(sqrt(a))


def nearest_agri_centers(farm, limit=5):
    """Ranks AgriCenter rows by straight-line distance from the farm's saved
    coordinates. Returns [] if the farm has no coordinates yet (same
    graceful-degradation pattern as weather.services)."""
    if farm.latitude is None or farm.longitude is None:
        return []
    farm_lat, farm_lon = float(farm.latitude), float(farm.longitude)
    ranked = []
    for center in AgriCenter.objects.all():
        distance_km = _haversine_km(farm_lat, farm_lon, float(center.latitude), float(center.longitude))
        ranked.append((distance_km, center))
    ranked.sort(key=lambda pair: pair[0])
    return [{'center': center, 'distance_km': round(distance_km)} for distance_km, center in ranked[:limit]]
