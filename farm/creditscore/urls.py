from django.urls import path

from . import api, public, views

app_name = 'creditscore'

urlpatterns = [
    path('', views.overview, name='overview'),
    path('recompute/', views.recompute, name='recompute'),
    path('data-sharing/', views.data_sharing, name='data_sharing'),
    path('data-sharing/<int:partner_id>/grant/', views.grant_consent, name='grant_consent'),
    path('data-sharing/<int:partner_id>/revoke/', views.revoke_consent, name='revoke_consent'),
    path('partners/apply/', public.partner_apply, name='partner_apply'),
    path('api/farms/<int:farm_id>/score/', api.farm_score, name='api_farm_score'),
]
