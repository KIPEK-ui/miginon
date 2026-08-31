from django.contrib import admin

from .models import FiqLedgerEntry, HederaConfig, MilkProductionCertificate


@admin.register(HederaConfig)
class HederaConfigAdmin(admin.ModelAdmin):
    list_display = ('cow_nft_token_id', 'harvest_nft_token_id', 'fiq_token_id', 'prediction_topic_id', 'finance_topic_id', 'credit_score_topic_id', 'updated_at')

    def has_add_permission(self, request):
        # Singleton - only ever pk=1, created automatically on first use.
        return not HederaConfig.objects.exists()


@admin.register(MilkProductionCertificate)
class MilkProductionCertificateAdmin(admin.ModelAdmin):
    list_display = ('farm', 'start_date', 'end_date', 'total_liters', 'fiq_amount', 'created_at')
    list_filter = ('farm',)


@admin.register(FiqLedgerEntry)
class FiqLedgerEntryAdmin(admin.ModelAdmin):
    list_display = ('farm', 'amount', 'reason', 'earned_by', 'created_at')
    list_filter = ('reason', 'farm')
