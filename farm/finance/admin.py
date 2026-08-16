from django.contrib import admin

from .models import Transaction


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ['farm', 'kind', 'category', 'amount', 'date']
    list_filter = ['kind', 'category', 'farm']
    date_hierarchy = 'date'
