from django.contrib import messages
from django.shortcuts import redirect
from django.urls import Resolver404, resolve
from django.utils.translation import gettext as _

from .demo import is_demo_user

# The only views the demo account may still POST to: establishing a
# DIFFERENT identity (login/signup/logout) has to keep working while
# viewing the demo, and theme/language are harmless per-visitor prefs, not
# farm data. Everything else the demo account tries to mutate - its own
# fake account settings included - gets blocked below.
_ALWAYS_ALLOWED_VIEWS = {
    'accounts:login_farm', 'accounts:login_email', 'accounts:login_otp', 'accounts:resend_login_otp',
    'accounts:admin_login', 'accounts:admin_login_otp', 'accounts:resend_admin_otp',
    'accounts:logout',
    'accounts:signup_account', 'accounts:signup_farm', 'accounts:signup_review',
    'accounts:signup_otp', 'accounts:resend_signup_otp',
    'core:set_theme', 'core:set_language',
}


class DemoModeMiddleware:
    """Makes the public /demo/ walkthrough safe to leave open to anyone:
    the demo account (core.demo.DEMO_USER_EMAIL, only ever reachable via
    core.views.demo_login) can navigate every real page, but any unsafe
    request it makes - other than the auth/prefs views above - is bounced
    back with a message instead of reaching the view. A single
    cross-cutting check rather than touching every view in every app: the
    whole point of this demo is that it's the real, unmodified app."""

    UNSAFE_METHODS = {'POST', 'PUT', 'PATCH', 'DELETE'}

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method in self.UNSAFE_METHODS and is_demo_user(request.user):
            try:
                view_name = resolve(request.path_info).view_name
            except Resolver404:
                view_name = None
            if view_name not in _ALWAYS_ALLOWED_VIEWS:
                messages.info(request, _("This is a read-only demo - sign up for your own farm to save changes."))
                return redirect(request.META.get('HTTP_REFERER') or 'farms:dashboard')
        return self.get_response(request)
