from django.urls import path

from . import views

app_name = 'notifications'

urlpatterns = [
    path('', views.notification_list, name='list'),
    path('push/subscribe/', views.push_subscribe, name='push_subscribe'),
]
