from django.contrib import admin

from .models import LandParcel


@admin.register(LandParcel)
class LandParcelAdmin(admin.ModelAdmin):
    list_display = ('name', 'farm', 'block', 'area_sqm', 'perimeter_m', 'created_by', 'created_at')
    list_filter = ('farm',)
    search_fields = ('name', 'farm__name')
