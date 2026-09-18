import math

EARTH_RADIUS_M = 6371000.0


def _haversine_m(p1, p2):
    lon1, lat1 = p1
    lon2, lat2 = p2
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def perimeter_m(coordinates):
    """coordinates: [[lng, lat], ...], an open ring - the closing segment
    back to the first point is added automatically."""
    ring = list(coordinates) + [coordinates[0]]
    return sum(_haversine_m(ring[i], ring[i + 1]) for i in range(len(ring) - 1))


def area_sqm(coordinates):
    """Spherical excess polygon area (the same formula the Google Maps and
    Leaflet.GeometryUtil area helpers use) - accurate for farm-sized plots,
    unlike a flat-plane shoelace formula which drifts away from the equator.
    Computed here server-side (never trusted from the client) so a saved
    parcel's stored numbers are authoritative regardless of what the
    on-map live readout happened to show while drawing."""
    if len(coordinates) < 3:
        return 0.0
    ring = list(coordinates) + [coordinates[0]]
    total = 0.0
    for i in range(len(ring) - 1):
        lon1, lat1 = math.radians(ring[i][0]), math.radians(ring[i][1])
        lon2, lat2 = math.radians(ring[i + 1][0]), math.radians(ring[i + 1][1])
        total += (lon2 - lon1) * (2 + math.sin(lat1) + math.sin(lat2))
    return abs(total * EARTH_RADIUS_M ** 2 / 2)
