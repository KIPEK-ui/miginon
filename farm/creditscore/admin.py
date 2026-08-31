from django.contrib import admin

from .models import CreditScoreSnapshot


@admin.register(CreditScoreSnapshot)
class CreditScoreSnapshotAdmin(admin.ModelAdmin):
    list_display = ('farm', 'score', 'tier', 'method', 'population_size', 'computed_at')
    list_filter = ('tier', 'method', 'farm')
