from django.urls import path

from . import views

app_name = 'core'

urlpatterns = [
    path('', views.landing, name='landing'),
    path('theme/', views.set_theme, name='set_theme'),
    path('language/', views.set_language, name='set_language'),
]
