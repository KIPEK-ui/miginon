from django.urls import path

from . import views

app_name = 'finance'

urlpatterns = [
    path('', views.transaction_list, name='transaction_list'),
    path('add/', views.transaction_create, name='transaction_create'),
    path('milk-sale/', views.milk_sale_create, name='milk_sale_create'),
    path('<int:transaction_id>/edit/', views.transaction_edit, name='transaction_edit'),
    path('<int:transaction_id>/delete/', views.transaction_delete, name='transaction_delete'),
]
