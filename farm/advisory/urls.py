from django.urls import path

from . import views

app_name = 'advisory'

urlpatterns = [
    path('', views.home, name='home'),
    path('diseases/', views.disease_list, name='disease_list'),
    path('diseases/<int:disease_id>/', views.disease_detail, name='disease_detail'),
    path('guides/', views.guide_list, name='guide_list'),
    path('guides/<int:guide_id>/', views.guide_detail, name='guide_detail'),
    path('agri-centers/', views.agri_centers, name='agri_centers'),
]
