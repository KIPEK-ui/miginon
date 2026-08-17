from django.contrib import admin

from .models import Cow, CowTransfer, FeedingRecord, MilkRecord


@admin.register(Cow)
class CowAdmin(admin.ModelAdmin):
    list_display = ['tag_id', 'name', 'farm', 'block', 'category', 'gender', 'status', 'created_at']
    list_filter = ['category', 'gender', 'status', 'farm']
    search_fields = ['tag_id', 'name', 'farm__name']


@admin.register(CowTransfer)
class CowTransferAdmin(admin.ModelAdmin):
    list_display = ['cow', 'farm', 'from_block', 'to_block', 'transferred_at']
    list_filter = ['farm']
    date_hierarchy = 'transferred_at'


@admin.register(FeedingRecord)
class FeedingRecordAdmin(admin.ModelAdmin):
    list_display = ['farm', 'block', 'date', 'session', 'cows_count', 'dairy_meal_kg', 'silage_hay_kg']
    list_filter = ['session', 'farm']
    date_hierarchy = 'date'


@admin.register(MilkRecord)
class MilkRecordAdmin(admin.ModelAdmin):
    list_display = ['farm', 'block', 'date', 'session', 'liters']
    list_filter = ['session', 'farm']
    date_hierarchy = 'date'
