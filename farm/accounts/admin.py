from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import EmailOTP, User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    ordering = ['-date_joined']
    list_display = ['email', 'first_name', 'last_name', 'platform_role', 'is_staff', 'is_active', 'date_joined']
    list_filter = ['platform_role', 'is_staff', 'is_active']
    search_fields = ['email', 'first_name', 'last_name', 'phone']
    readonly_fields = ['date_joined', 'last_login', 'last_login_at']
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'phone')}),
        ('Role & permissions', {
            'fields': ('platform_role', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')
        }),
        ('Important dates', {'fields': ('last_login', 'last_login_at', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'first_name', 'last_name', 'password1', 'password2', 'is_staff', 'is_superuser'),
        }),
    )


@admin.register(EmailOTP)
class EmailOTPAdmin(admin.ModelAdmin):
    list_display = ['email', 'purpose', 'farm', 'code', 'is_used', 'attempts', 'created_at', 'expires_at']
    list_filter = ['purpose', 'is_used']
    search_fields = ['email']
