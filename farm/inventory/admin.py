from django.contrib import admin

from .models import InventoryItem, StockMovement


@admin.register(InventoryItem)
class InventoryItemAdmin(admin.ModelAdmin):
    list_display = ['name', 'farm', 'category', 'unit', 'current_stock', 'reorder_level']
    list_filter = ['category', 'farm']
    search_fields = ['name', 'farm__name']


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ['item', 'farm', 'date', 'movement_type', 'quantity']
    list_filter = ['movement_type', 'farm']
    date_hierarchy = 'date'
