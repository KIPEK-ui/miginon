from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['farm', 'actor', 'verb', 'kind', 'description', 'created_at']
    list_filter = ['verb', 'kind', 'farm']
    search_fields = ['description', 'actor__email']
    date_hierarchy = 'created_at'
