from django.contrib import admin

from .models import Block, Farm, FarmMembership


class BlockInline(admin.TabularInline):
    model = Block
    extra = 0


class MembershipInline(admin.TabularInline):
    model = FarmMembership
    extra = 0


@admin.register(Farm)
class FarmAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'owner', 'location', 'is_active', 'created_at']
    list_filter = ['is_active']
    search_fields = ['name', 'code', 'owner__email']
    readonly_fields = ['code']
    inlines = [BlockInline, MembershipInline]


@admin.register(FarmMembership)
class FarmMembershipAdmin(admin.ModelAdmin):
    list_display = ['user', 'farm', 'role', 'status', 'invited_by', 'created_at']
    list_filter = ['role', 'status']
    search_fields = ['user__email', 'farm__name', 'farm__code']


@admin.register(Block)
class BlockAdmin(admin.ModelAdmin):
    list_display = ['name', 'farm', 'active_cow_count', 'created_at']
    search_fields = ['name', 'farm__name']
