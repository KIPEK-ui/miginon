from django.contrib import admin

from .models import FarmInsight


@admin.register(FarmInsight)
class FarmInsightAdmin(admin.ModelAdmin):
    list_display = ('farm', 'title', 'category', 'severity', 'computed_at')
    list_filter = ('category', 'severity')
    search_fields = ('farm__name', 'title')
