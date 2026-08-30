from django.contrib import admin

from .models import AgriCenter, DiseaseCatalog, Guide


@admin.register(DiseaseCatalog)
class DiseaseCatalogAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'affected')
    list_filter = ('category',)
    search_fields = ('name', 'affected')


@admin.register(Guide)
class GuideAdmin(admin.ModelAdmin):
    list_display = ('title', 'category')
    list_filter = ('category',)
    search_fields = ('title',)


@admin.register(AgriCenter)
class AgriCenterAdmin(admin.ModelAdmin):
    list_display = ('name', 'county', 'town', 'focus_area')
    list_filter = ('county',)
    search_fields = ('name', 'county', 'town')
