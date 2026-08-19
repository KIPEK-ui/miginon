from django.urls import path

from . import views

app_name = 'analysis'

urlpatterns = [
    path('', views.overview, name='overview'),
    path('export/', views.export, name='export'),
    path('export/email/', views.email_report, name='email_report'),

    path('predictions/', views.predictions_overview, name='predictions_overview'),
    path('predictions/block/<int:block_id>/', views.predictions_block, name='predictions_block'),
    path('predictions/cow/<int:cow_id>/', views.predictions_cow, name='predictions_cow'),
]
