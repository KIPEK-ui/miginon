from django.urls import path

from . import views

app_name = 'creditscore'

urlpatterns = [
    path('', views.overview, name='overview'),
    path('recompute/', views.recompute, name='recompute'),
]
