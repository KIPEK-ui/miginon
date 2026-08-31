from django.urls import path

from . import views

app_name = 'blockchain'

urlpatterns = [
    path('wallet/', views.wallet_view, name='wallet'),
    path('certificates/mint/', views.certificate_create, name='certificate_create'),
    path('rewards/worker/', views.worker_reward_create, name='worker_reward_create'),
]
