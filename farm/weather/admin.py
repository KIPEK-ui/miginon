from django.contrib import admin

from .models import WeatherCache


@admin.register(WeatherCache)
class WeatherCacheAdmin(admin.ModelAdmin):
    list_display = ['farm', 'fetched_at', 'advisory_key']
    list_filter = ['advisory_key']
    search_fields = ['farm__name']
