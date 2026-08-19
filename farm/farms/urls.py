from django.urls import path

from . import views

app_name = 'farms'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('switch/<int:farm_id>/', views.switch_farm, name='switch_farm'),
    path('add/', views.add_farm, name='add_farm'),
    path('settings/', views.farm_settings, name='farm_settings'),

    path('welcome/', views.signup_complete, name='signup_complete'),
    path('setup/block/', views.setup_block, name='setup_block'),
    path('setup/cow/', views.setup_cow, name='setup_cow'),

    path('workers/', views.worker_list, name='worker_list'),
    path('workers/invite/', views.worker_invite, name='worker_invite'),
    path('workers/<int:membership_id>/role/', views.worker_update_role, name='worker_update_role'),
    path('workers/<int:membership_id>/suspend/', views.worker_suspend, name='worker_suspend'),

    path('blocks/', views.block_list, name='block_list'),
    path('map/', views.farm_map, name='farm_map'),
    path('blocks/add/', views.block_create, name='block_create'),
    path('blocks/<int:block_id>/', views.block_detail, name='block_detail'),
    path('blocks/<int:block_id>/edit/', views.block_edit, name='block_edit'),
    path('blocks/<int:block_id>/delete/', views.block_delete, name='block_delete'),

    path('admin/', views.platform_dashboard, name='admin_dashboard'),
    path('admin/farms/<int:farm_id>/toggle/', views.admin_toggle_farm, name='admin_toggle_farm'),
    path('admin/users/<int:user_id>/toggle/', views.admin_toggle_user, name='admin_toggle_user'),
]
