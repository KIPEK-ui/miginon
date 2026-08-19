from django.urls import path

from . import views

app_name = 'accounts'

urlpatterns = [
    # Farm-scoped login: farm ID -> email -> OTP
    path('login/', views.login_farm, name='login_farm'),
    path('login/email/', views.login_email, name='login_email'),
    path('login/otp/', views.login_otp, name='login_otp'),
    path('login/otp/resend/', views.resend_login_otp, name='resend_login_otp'),

    # Platform admin login: email -> OTP (no farm ID)
    path('admin-login/', views.admin_login, name='admin_login'),
    path('admin-login/otp/', views.admin_login_otp, name='admin_login_otp'),
    path('admin-login/otp/resend/', views.resend_admin_otp, name='resend_admin_otp'),

    path('logout/', views.logout_view, name='logout'),

    # Signup wizard: account -> farm -> review -> OTP
    path('signup/', views.signup_step_account, name='signup_account'),
    path('signup/farm/', views.signup_step_farm, name='signup_farm'),
    path('signup/review/', views.signup_review, name='signup_review'),
    path('signup/otp/', views.signup_otp, name='signup_otp'),
    path('signup/otp/resend/', views.resend_signup_otp, name='resend_signup_otp'),

    # Settings: profile + change email
    path('settings/', views.settings_view, name='settings'),
    path('settings/notifications/', views.settings_notifications, name='settings_notifications'),
    path('settings/delete/', views.delete_account, name='delete_account'),
    path('settings/email/', views.settings_email, name='settings_email'),
    path('settings/email/otp/', views.settings_email_otp, name='settings_email_otp'),
    path('settings/email/otp/resend/', views.resend_settings_email_otp, name='resend_settings_email_otp'),
]
