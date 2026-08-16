from django.urls import path

from . import views

app_name = 'cows'

urlpatterns = [
    path('', views.cow_list, name='cow_list'),
    path('add/', views.cow_create, name='cow_create'),
    path('<int:cow_id>/', views.cow_detail, name='cow_detail'),
    path('<int:cow_id>/edit/', views.cow_edit, name='cow_edit'),
    path('<int:cow_id>/delete/', views.cow_delete, name='cow_delete'),
    path('<int:cow_id>/transfer/', views.cow_transfer, name='cow_transfer'),

    path('feeding/', views.feeding_list, name='feeding_list'),
    path('feeding/add/', views.feeding_create, name='feeding_create'),
    path('feeding/<int:record_id>/edit/', views.feeding_edit, name='feeding_edit'),
    path('feeding/<int:record_id>/delete/', views.feeding_delete, name='feeding_delete'),

    path('milk/', views.milk_list, name='milk_list'),
    path('milk/add/', views.milk_create, name='milk_create'),
    path('milk/<int:record_id>/edit/', views.milk_edit, name='milk_edit'),
    path('milk/<int:record_id>/delete/', views.milk_delete, name='milk_delete'),
]
