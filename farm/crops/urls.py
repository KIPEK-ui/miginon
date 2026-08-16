from django.urls import path

from . import views

app_name = 'crops'

urlpatterns = [
    path('', views.crop_list, name='crop_list'),
    path('add/', views.crop_create, name='crop_create'),
    path('<int:crop_id>/', views.crop_detail, name='crop_detail'),
    path('<int:crop_id>/edit/', views.crop_edit, name='crop_edit'),
    path('<int:crop_id>/delete/', views.crop_delete, name='crop_delete'),

    path('activity/', views.activity_list, name='activity_list'),
    path('activity/add/', views.activity_create, name='activity_create'),
    path('activity/<int:activity_id>/edit/', views.activity_edit, name='activity_edit'),
    path('activity/<int:activity_id>/delete/', views.activity_delete, name='activity_delete'),
]
