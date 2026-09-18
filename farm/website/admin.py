from django.contrib import admin

from .models import FarmSite, Order, Product, SitePage


class SitePageInline(admin.TabularInline):
    model = SitePage
    extra = 0


@admin.register(FarmSite)
class FarmSiteAdmin(admin.ModelAdmin):
    list_display = ('farm', 'slug', 'is_published', 'updated_at')
    list_filter = ('is_published',)
    search_fields = ('farm__name', 'slug')
    inlines = [SitePageInline]


@admin.register(SitePage)
class SitePageAdmin(admin.ModelAdmin):
    list_display = ('site', 'title', 'slug', 'template', 'order')
    list_filter = ('template',)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'farm', 'price', 'unit', 'is_available')
    list_filter = ('is_available',)
    search_fields = ('name', 'farm__name')


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('buyer_name', 'product', 'quantity', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('buyer_name', 'buyer_phone', 'product__name')
