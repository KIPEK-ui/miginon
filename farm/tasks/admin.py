from django.contrib import admin

from .models import Task


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ['title', 'farm', 'assigned_to', 'status', 'priority', 'due_date']
    list_filter = ['status', 'priority', 'farm']
    search_fields = ['title', 'farm__name']
