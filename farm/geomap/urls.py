from django.urls import path

from . import views

app_name = 'geomap'

urlpatterns = [
    path('', views.parcel_map, name='map'),
    path('save/', views.parcel_create, name='parcel_create'),
    path('<int:parcel_id>/delete/', views.parcel_delete, name='parcel_delete'),
]
