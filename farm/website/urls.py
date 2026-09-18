from django.urls import path

from . import views

app_name = 'website'

urlpatterns = [
    path('', views.site_settings, name='site_settings'),
    path('pages/', views.page_list, name='page_list'),
    path('pages/add/', views.page_create, name='page_create'),
    path('pages/<int:page_id>/edit/', views.page_edit, name='page_edit'),
    path('pages/<int:page_id>/delete/', views.page_delete, name='page_delete'),

    path('products/', views.product_list, name='product_list'),
    path('products/add/', views.product_create, name='product_create'),
    path('products/<int:product_id>/edit/', views.product_edit, name='product_edit'),
    path('products/<int:product_id>/delete/', views.product_delete, name='product_delete'),

    path('orders/', views.order_list, name='order_list'),
    path('orders/<int:order_id>/status/', views.order_status_update, name='order_status_update'),
]
