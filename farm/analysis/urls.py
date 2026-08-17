from django.urls import path

from . import views

app_name = 'analysis'

urlpatterns = [
    path('', views.overview, name='overview'),
    path('export/', views.export, name='export'),
    path('export/email/', views.email_report, name='email_report'),
]
