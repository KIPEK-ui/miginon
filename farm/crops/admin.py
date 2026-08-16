from django.contrib import admin

from .models import Crop, CropActivity


@admin.register(Crop)
class CropAdmin(admin.ModelAdmin):
    list_display = ['name', 'farm', 'field_name', 'status', 'planted_on', 'expected_harvest']
    list_filter = ['status', 'farm']
    search_fields = ['name', 'farm__name']


@admin.register(CropActivity)
class CropActivityAdmin(admin.ModelAdmin):
    list_display = ['crop', 'farm', 'date', 'activity_type', 'quantity_harvested_kg']
    list_filter = ['activity_type', 'farm']
    date_hierarchy = 'date'
