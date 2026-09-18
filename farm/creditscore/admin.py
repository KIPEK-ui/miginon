from django.contrib import admin, messages

from core.email import send_styled_email_safely

from .models import CreditScoreSnapshot, DataPartner, DataShareConsent


@admin.register(CreditScoreSnapshot)
class CreditScoreSnapshotAdmin(admin.ModelAdmin):
    list_display = ('farm', 'score', 'tier', 'method', 'population_size', 'computed_at')
    list_filter = ('tier', 'method', 'farm')


@admin.action(description='Approve selected partners and email their API key')
def approve_and_notify(modeladmin, request, queryset):
    pending = queryset.filter(status=DataPartner.Status.PENDING)
    for partner in pending:
        partner.status = DataPartner.Status.APPROVED
        partner.save(update_fields=['status'])
        if partner.contact_email:
            # Non-critical, like every other outbound notification in this
            # codebase (see send_styled_email_safely's docstring) - a
            # ZeptoMail hiccup shouldn't undo the approval, since the key
            # is also visible to staff in this admin either way.
            send_styled_email_safely(
                to=partner.contact_email,
                subject='Your FarmIQ data partner access is approved',
                template_name='emails/partner_approved.html',
                context={'partner': partner},
            )
    modeladmin.message_user(request, f'Approved {pending.count()} partner(s).', level=messages.SUCCESS)


@admin.register(DataPartner)
class DataPartnerAdmin(admin.ModelAdmin):
    # api_key is generated on save (see DataPartner.save) and shown
    # read-only rather than editable, so it can't be overwritten by accident
    # once a partner is already using it.
    list_display = ('name', 'slug', 'status', 'contact_email', 'created_at')
    list_filter = ('status',)
    search_fields = ('name', 'slug', 'contact_email')
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ('api_key', 'created_at')
    actions = [approve_and_notify]


@admin.register(DataShareConsent)
class DataShareConsentAdmin(admin.ModelAdmin):
    list_display = ('farm', 'partner', 'granted_by', 'granted_at', 'revoked_at')
    list_filter = ('partner',)
    autocomplete_fields = ('farm', 'partner')
    readonly_fields = ('granted_at',)
