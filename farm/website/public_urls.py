from django.urls import path

from . import views

app_name = 'website_public'

urlpatterns = [
    # A 3-segment path, so it can never collide with a farm's own page slug
    # at <slug>/<page_slug>/ below (that pattern only ever matches 2
    # segments) - no reserved-word bookkeeping needed for "products"/"order".
    path('<slug:slug>/products/order/', views.order_create, name='order_create'),
    path('<slug:slug>/', views.public_home, name='home'),
    path('<slug:slug>/<slug:page_slug>/', views.public_page, name='page'),
]
