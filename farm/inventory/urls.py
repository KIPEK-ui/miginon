from django.urls import path

from . import views

app_name = 'inventory'

urlpatterns = [
    path('', views.item_list, name='item_list'),
    path('add/', views.item_create, name='item_create'),
    path('<int:item_id>/', views.item_detail, name='item_detail'),
    path('<int:item_id>/edit/', views.item_edit, name='item_edit'),
    path('<int:item_id>/composition/', views.item_composition, name='item_composition'),
    path('<int:item_id>/delete/', views.item_delete, name='item_delete'),

    path('movements/', views.movement_list, name='movement_list'),
    path('movements/add/', views.movement_create, name='movement_create'),
    path('milk-usage/', views.milk_usage_create, name='milk_usage_create'),
    path('movements/<int:movement_id>/delete/', views.movement_delete, name='movement_delete'),
]
