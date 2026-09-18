from django.conf import settings
from django.db import models


class LandParcel(models.Model):
    """A GPS-surveyed farm boundary or field, drawn on the GeoMap page (see
    geomap.views.parcel_map) - deliberately separate from farms.Block so a
    farmer can map the whole farm's outer boundary as its own shape, not
    just individual paddocks. Optionally linked to a Block afterwards."""

    farm = models.ForeignKey('farms.Farm', on_delete=models.CASCADE, related_name='land_parcels')
    block = models.ForeignKey(
        'farms.Block', null=True, blank=True, on_delete=models.SET_NULL, related_name='land_parcels',
    )
    name = models.CharField(max_length=100)
    # [[lng, lat], [lng, lat], ...] - GeoJSON coordinate order (lng first),
    # an open ring (the closing point back to the start is implied, not
    # duplicated in storage).
    coordinates = models.JSONField()
    area_sqm = models.DecimalField(max_digits=12, decimal_places=2)
    perimeter_m = models.DecimalField(max_digits=10, decimal_places=2)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.name} - {self.farm.name}'

    @property
    def area_ha(self):
        return self.area_sqm / 10000
