from django.urls import path

from . import views

app_name = 'weather'

urlpatterns = [
    path('', views.forecast_view, name='forecast'),
    path('refresh/', views.refresh_view, name='refresh'),
]
