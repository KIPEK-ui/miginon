import logging

from django.contrib import messages
from django.contrib.auth import login as django_login
from django.contrib.auth import logout as django_logout
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _

from core.email import send_styled_email_safely
from farms.kenya_data import COUNTY_TOWNS
from farms.models import Farm, FarmMembership, FarmRole
from farms.services import geocode_farm_location
from notifications.models import Notification
from notifications.services import notify

from .forms import (
    EmailChangeForm,
    EmailLoginForm,
    FarmCodeForm,
    NotificationPreferenceForm,
    OTPForm,
    ProfileForm,
    SignupAccountForm,
    SignupFarmForm,
)
from .models import EmailOTP, User
from .services import OTPDeliveryError, can_resend, issue_otp

logger = logging.getLogger(__name__)

SIGNUP_ACCOUNT_KEY = 'signup_account'
SIGNUP_FARM_KEY = 'signup_farm'
EMAIL_CHANGE_KEY = 'pending_new_email'


def csrf_failure(request, reason=''):
    """Global CSRF failure handler (see CSRF_FAILURE_VIEW in settings) -
    logs the failing request (visible in Vercel's function logs, so a
    stale/rejected request is actually diagnosable instead of just a report
    of "it happened") and gracefully carries the user onward instead of
    dead-ending on Django's raw 403 page: back to the dashboard if their
    session is fine and it was just this one form's token that went stale,
    otherwise back to a fresh login start."""
    logger.warning(
        'CSRF failure: reason=%r path=%s method=%s referer=%s user=%s has_sessionid=%s has_csrftoken=%s ua=%s',
        reason, request.path, request.method, request.META.get('HTTP_REFERER', ''),
        request.user if request.user.is_authenticated else 'anonymous',
        'sessionid' in request.COOKIES, 'csrftoken' in request.COOKIES,
        request.META.get('HTTP_USER_AGENT', ''),
    )
    destination = reverse('farms:dashboard') if request.user.is_authenticated else reverse('accounts:login_farm')
    return render(request, 'accounts/csrf_failure.html', {'destination': destination}, status=403)


def _already_authenticated_redirect(request):
    if request.user.is_authenticated:
        return redirect('farms:dashboard')
    return None


def _login_redirect(target, user):
    """redirect(target), plus the LANGUAGE_COOKIE set from the user's saved
    preference - LocaleMiddleware is cookie-only (no session-based language
    key as of Django 4+), so this is what makes a language choice saved on
    one device show up on a fresh login elsewhere."""
    response = redirect(target)
    response.set_cookie(
        settings.LANGUAGE_COOKIE_NAME, user.language,
        max_age=settings.LANGUAGE_COOKIE_AGE or 60 * 60 * 24 * 365,
    )
    return response


def _try_issue_otp(request, email, purpose, farm=None):
    """issue_otp(), but turned into a friendly retry message instead of a
    raw 500 when the email provider rejects or throttles the send (e.g. an
    SMTP quota/abuse block). Returns True on success, False on failure."""
    try:
        issue_otp(email, purpose, farm=farm)
        return True
    except OTPDeliveryError:
        messages.error(
            request,
            _("We couldn't send the verification code right now. Please wait a moment and try again.")
        )
        return False


# ---------------------------------------------------------------- farm login

def login_farm(request):
    redirect_resp = _already_authenticated_redirect(request)
    if redirect_resp:
        return redirect_resp

    form = FarmCodeForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        code = form.cleaned_data['code']
        try:
            farm = Farm.objects.get(code=code, is_active=True)
        except Farm.DoesNotExist:
            form.add_error('code', _("We couldn't find a farm with that ID. Double-check the code and try again."))
        else:
            request.session['login_farm_id'] = farm.id
            request.session['login_farm_code'] = farm.code
            request.session['login_farm_name'] = farm.name
            request.session.pop('login_email', None)
            request.session.pop('login_role', None)
            return redirect('accounts:login_email')

    return render(request, 'accounts/login_farm.html', {'form': form, 'step': 1})


def login_email(request):
    redirect_resp = _already_authenticated_redirect(request)
    if redirect_resp:
        return redirect_resp

    farm_id = request.session.get('login_farm_id')
    if not farm_id:
        return redirect('accounts:login_farm')
    farm = Farm.objects.filter(id=farm_id, is_active=True).first()
    if not farm:
        return redirect('accounts:login_farm')

    form = EmailLoginForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        email = form.cleaned_data['email']
        membership = (
            FarmMembership.objects.filter(
                farm=farm, user__email=email, status=FarmMembership.Status.ACTIVE
            )
            .select_related('user')
            .first()
        )
        if not membership:
            form.add_error(
                'email',
                _('No account found for this email at %(farm)s. '
                  'Ask the farm owner to add you as a worker, or sign up to create your own farm.')
                % {'farm': farm.name}
            )
        elif _try_issue_otp(request, email, EmailOTP.Purpose.LOGIN, farm=farm):
            request.session['login_email'] = email
            request.session['login_role'] = membership.get_role_display()
            messages.success(request, _('A 6-digit code was sent to %(email)s.') % {'email': email})
            return redirect('accounts:login_otp')

    return render(request, 'accounts/login_email.html', {'form': form, 'farm': farm, 'step': 2})


def login_otp(request):
    redirect_resp = _already_authenticated_redirect(request)
    if redirect_resp:
        return redirect_resp

    farm_id = request.session.get('login_farm_id')
    email = request.session.get('login_email')
    if not farm_id or not email:
        return redirect('accounts:login_farm')
    farm = Farm.objects.filter(id=farm_id, is_active=True).first()
    if not farm:
        return redirect('accounts:login_farm')

    form = OTPForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        code = form.cleaned_data['code']
        otp = (
            EmailOTP.objects.filter(email=email, farm=farm, purpose=EmailOTP.Purpose.LOGIN, is_used=False)
            .order_by('-created_at')
            .first()
        )
        if not otp or not otp.is_valid():
            form.add_error('code', _('That code has expired. Request a new one below.'))
        elif otp.code != code:
            otp.register_failed_attempt()
            form.add_error('code', _('Incorrect code. Please try again.'))
        else:
            otp.is_used = True
            otp.save(update_fields=['is_used'])
            user = User.objects.get(email=email)
            user.last_login_at = timezone.now()
            user.save(update_fields=['last_login_at'])
            django_login(request, user)
            request.session['active_farm_id'] = farm.id
            for key in ('login_farm_id', 'login_farm_code', 'login_farm_name', 'login_email', 'login_role'):
                request.session.pop(key, None)
            messages.success(request, _('Welcome back, %(name)s!') % {'name': user.get_short_name()})
            return _login_redirect('farms:dashboard', user)

    last_otp = (
        EmailOTP.objects.filter(email=email, farm=farm, purpose=EmailOTP.Purpose.LOGIN)
        .order_by('-created_at')
        .first()
    )
    context = {
        'form': form,
        'farm': farm,
        'email': email,
        'role': request.session.get('login_role'),
        'step': 3,
        'can_resend': can_resend(last_otp),
    }
    return render(request, 'accounts/login_otp.html', context)


def resend_login_otp(request):
    if request.method != 'POST':
        return redirect('accounts:login_farm')
    farm_id = request.session.get('login_farm_id')
    email = request.session.get('login_email')
    if not farm_id or not email:
        return redirect('accounts:login_farm')
    farm = Farm.objects.filter(id=farm_id).first()
    last_otp = (
        EmailOTP.objects.filter(email=email, farm=farm, purpose=EmailOTP.Purpose.LOGIN)
        .order_by('-created_at')
        .first()
    )
    if can_resend(last_otp):
        if _try_issue_otp(request, email, EmailOTP.Purpose.LOGIN, farm=farm):
            messages.success(request, _('A new code is on its way.'))
    else:
        messages.warning(request, _('Please wait a little before requesting another code.'))
    return redirect('accounts:login_otp')


# ------------------------------------------------------------ platform admin

def admin_login(request):
    redirect_resp = _already_authenticated_redirect(request)
    if redirect_resp:
        return redirect_resp

    form = EmailLoginForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        email = form.cleaned_data['email']
        user = User.objects.filter(email=email).first()
        if not user or not user.is_platform_admin:
            form.add_error('email', _('No platform admin account matches this email.'))
        elif _try_issue_otp(request, email, EmailOTP.Purpose.LOGIN, farm=None):
            request.session['admin_login_email'] = email
            messages.success(request, _('A 6-digit code was sent to %(email)s.') % {'email': email})
            return redirect('accounts:admin_login_otp')

    return render(request, 'accounts/admin_login.html', {'form': form})


def admin_login_otp(request):
    redirect_resp = _already_authenticated_redirect(request)
    if redirect_resp:
        return redirect_resp

    email = request.session.get('admin_login_email')
    if not email:
        return redirect('accounts:admin_login')

    form = OTPForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        code = form.cleaned_data['code']
        otp = (
            EmailOTP.objects.filter(email=email, farm=None, purpose=EmailOTP.Purpose.LOGIN, is_used=False)
            .order_by('-created_at')
            .first()
        )
        if not otp or not otp.is_valid():
            form.add_error('code', _('That code has expired. Request a new one below.'))
        elif otp.code != code:
            otp.register_failed_attempt()
            form.add_error('code', _('Incorrect code. Please try again.'))
        else:
            otp.is_used = True
            otp.save(update_fields=['is_used'])
            user = User.objects.get(email=email)
            django_login(request, user)
            request.session.pop('admin_login_email', None)
            return _login_redirect('farms:dashboard', user)

    last_otp = (
        EmailOTP.objects.filter(email=email, farm=None, purpose=EmailOTP.Purpose.LOGIN)
        .order_by('-created_at')
        .first()
    )
    context = {'form': form, 'email': email, 'can_resend': can_resend(last_otp)}
    return render(request, 'accounts/admin_login_otp.html', context)


def resend_admin_otp(request):
    if request.method != 'POST':
        return redirect('accounts:admin_login')
    email = request.session.get('admin_login_email')
    if not email:
        return redirect('accounts:admin_login')
    last_otp = (
        EmailOTP.objects.filter(email=email, farm=None, purpose=EmailOTP.Purpose.LOGIN)
        .order_by('-created_at')
        .first()
    )
    if can_resend(last_otp):
        if _try_issue_otp(request, email, EmailOTP.Purpose.LOGIN, farm=None):
            messages.success(request, _('A new code is on its way.'))
    else:
        messages.warning(request, _('Please wait a little before requesting another code.'))
    return redirect('accounts:admin_login_otp')


# --------------------------------------------------------------------- logout

def logout_view(request):
    django_logout(request)
    messages.success(request, _('You have been signed out.'))
    return redirect('core:landing')


# ---------------------------------------------------------------- signup wizard

def signup_step_account(request):
    redirect_resp = _already_authenticated_redirect(request)
    if redirect_resp:
        return redirect_resp

    initial = request.session.get(SIGNUP_ACCOUNT_KEY)
    form = SignupAccountForm(request.POST or None, initial=initial)
    if request.method == 'POST' and form.is_valid():
        request.session[SIGNUP_ACCOUNT_KEY] = form.cleaned_data
        return redirect('accounts:signup_farm')
    return render(request, 'accounts/signup_account.html', {'form': form, 'step': 1})


def signup_step_farm(request):
    redirect_resp = _already_authenticated_redirect(request)
    if redirect_resp:
        return redirect_resp
    if SIGNUP_ACCOUNT_KEY not in request.session:
        return redirect('accounts:signup_account')

    initial = request.session.get(SIGNUP_FARM_KEY)
    form = SignupFarmForm(request.POST or None, initial=initial)
    if request.method == 'POST' and form.is_valid():
        request.session[SIGNUP_FARM_KEY] = form.cleaned_data
        return redirect('accounts:signup_review')
    return render(request, 'accounts/signup_farm.html', {'form': form, 'step': 2, 'county_towns': COUNTY_TOWNS})


def signup_review(request):
    redirect_resp = _already_authenticated_redirect(request)
    if redirect_resp:
        return redirect_resp
    account = request.session.get(SIGNUP_ACCOUNT_KEY)
    farm = request.session.get(SIGNUP_FARM_KEY)
    if not account or not farm:
        return redirect('accounts:signup_account')

    if request.method == 'POST':
        if _try_issue_otp(request, account['email'], EmailOTP.Purpose.SIGNUP, farm=None):
            messages.success(request, _('A 6-digit code was sent to %(email)s.') % {'email': account['email']})
            return redirect('accounts:signup_otp')

    return render(
        request, 'accounts/signup_review.html',
        {'account': account, 'farm': farm, 'country_name': 'Kenya', 'step': 3},
    )


def signup_otp(request):
    redirect_resp = _already_authenticated_redirect(request)
    if redirect_resp:
        return redirect_resp
    account = request.session.get(SIGNUP_ACCOUNT_KEY)
    farm_data = request.session.get(SIGNUP_FARM_KEY)
    if not account or not farm_data:
        return redirect('accounts:signup_account')

    email = account['email']
    form = OTPForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        code = form.cleaned_data['code']
        otp = (
            EmailOTP.objects.filter(email=email, farm=None, purpose=EmailOTP.Purpose.SIGNUP, is_used=False)
            .order_by('-created_at')
            .first()
        )
        if not otp or not otp.is_valid():
            form.add_error('code', _('That code has expired. Request a new one below.'))
        elif otp.code != code:
            otp.register_failed_attempt()
            form.add_error('code', _('Incorrect code. Please try again.'))
        else:
            otp.is_used = True
            otp.save(update_fields=['is_used'])

            user = User.objects.create_user(
                email=email,
                first_name=account['first_name'],
                last_name=account.get('last_name', ''),
                phone=account.get('phone', ''),
            )
            farm = Farm.objects.create(
                name=farm_data['farm_name'],
                owner=user,
                country=farm_data.get('country', 'KE'),
                county=farm_data.get('county', ''),
                location=farm_data.get('location', ''),
            )
            geocode_farm_location(farm)
            FarmMembership.objects.create(
                user=user, farm=farm, role=FarmRole.FARMER, status=FarmMembership.Status.ACTIVE,
            )
            notify(farm, user, Notification.Verb.CREATED, 'farm', farm.name)
            send_styled_email_safely(
                to=user.email,
                subject=_('Welcome to FarmIQ - your Farm ID is %(code)s') % {'code': farm.code},
                template_name='emails/welcome.html',
                context={
                    'user': user, 'farm': farm,
                    'login_url': request.build_absolute_uri(reverse('accounts:login_farm')),
                },
            )
            django_login(request, user)
            request.session['active_farm_id'] = farm.id
            request.session['new_farm_id'] = farm.id
            for key in (SIGNUP_ACCOUNT_KEY, SIGNUP_FARM_KEY):
                request.session.pop(key, None)
            return _login_redirect('farms:signup_complete', user)

    last_otp = (
        EmailOTP.objects.filter(email=email, farm=None, purpose=EmailOTP.Purpose.SIGNUP)
        .order_by('-created_at')
        .first()
    )
    context = {'form': form, 'email': email, 'step': 4, 'can_resend': can_resend(last_otp)}
    return render(request, 'accounts/signup_otp.html', context)


def resend_signup_otp(request):
    if request.method != 'POST':
        return redirect('accounts:signup_account')
    account = request.session.get(SIGNUP_ACCOUNT_KEY)
    if not account:
        return redirect('accounts:signup_account')
    email = account['email']
    last_otp = (
        EmailOTP.objects.filter(email=email, farm=None, purpose=EmailOTP.Purpose.SIGNUP)
        .order_by('-created_at')
        .first()
    )
    if can_resend(last_otp):
        if _try_issue_otp(request, email, EmailOTP.Purpose.SIGNUP, farm=None):
            messages.success(request, _('A new code is on its way.'))
    else:
        messages.warning(request, _('Please wait a little before requesting another code.'))
    return redirect('accounts:signup_otp')


# --------------------------------------------------------------------- settings

@login_required
def settings_view(request):
    form = ProfileForm(request.POST or None, instance=request.user)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, _('Profile updated.'))
        return redirect('accounts:settings')
    notification_form = NotificationPreferenceForm(instance=request.user)
    return render(request, 'accounts/settings.html', {'form': form, 'notification_form': notification_form})


@login_required
def settings_notifications(request):
    form = NotificationPreferenceForm(request.POST or None, instance=request.user)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, _('Notification preference updated.'))
    return redirect('accounts:settings')


@login_required
def delete_account(request):
    """Self-service account deletion. Farm.owner and FarmMembership.user are
    both on_delete=CASCADE, so deleting the user is enough by itself: for
    any farm they *own*, the whole farm (blocks, herd, records, everyone
    else's membership - everything) cascades away with them; for any farm
    they're just a member of, only their own membership (and personal
    records like push subscriptions) is removed - the farm and its data are
    untouched for the rest of the team."""
    memberships = FarmMembership.objects.filter(
        user=request.user, status=FarmMembership.Status.ACTIVE
    ).select_related('farm')
    owned_memberships = [m for m in memberships if m.role == FarmRole.FARMER]
    other_memberships = [m for m in memberships if m.role != FarmRole.FARMER]

    if request.method == 'POST':
        if request.POST.get('confirm', '').strip().upper() != 'DELETE':
            messages.error(request, _('Type DELETE to confirm.'))
        else:
            user = request.user
            django_logout(request)
            user.delete()
            messages.success(request, _('Your account has been deleted.'))
            return redirect('core:landing')

    return render(request, 'accounts/delete_account.html', {
        'owned_memberships': owned_memberships,
        'other_memberships': other_memberships,
    })


@login_required
def settings_email(request):
    form = EmailChangeForm(request.POST or None, user=request.user)
    if request.method == 'POST' and form.is_valid():
        new_email = form.cleaned_data['new_email']
        if _try_issue_otp(request, new_email, EmailOTP.Purpose.EMAIL_CHANGE, farm=None):
            request.session[EMAIL_CHANGE_KEY] = new_email
            messages.success(request, _('A 6-digit code was sent to %(email)s.') % {'email': new_email})
            return redirect('accounts:settings_email_otp')
    return render(request, 'accounts/settings_email.html', {'form': form})


@login_required
def settings_email_otp(request):
    new_email = request.session.get(EMAIL_CHANGE_KEY)
    if not new_email:
        return redirect('accounts:settings_email')

    form = OTPForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        code = form.cleaned_data['code']
        otp = (
            EmailOTP.objects.filter(email=new_email, farm=None, purpose=EmailOTP.Purpose.EMAIL_CHANGE, is_used=False)
            .order_by('-created_at')
            .first()
        )
        if not otp or not otp.is_valid():
            form.add_error('code', _('That code has expired. Request a new one below.'))
        elif otp.code != code:
            otp.register_failed_attempt()
            form.add_error('code', _('Incorrect code. Please try again.'))
        elif User.objects.filter(email=new_email).exists():
            form.add_error(None, _('That email was just taken by another account.'))
        else:
            otp.is_used = True
            otp.save(update_fields=['is_used'])
            request.user.email = new_email
            request.user.save(update_fields=['email'])
            request.session.pop(EMAIL_CHANGE_KEY, None)
            messages.success(request, _('Your email address has been updated.'))
            return redirect('accounts:settings')

    last_otp = (
        EmailOTP.objects.filter(email=new_email, farm=None, purpose=EmailOTP.Purpose.EMAIL_CHANGE)
        .order_by('-created_at')
        .first()
    )
    context = {'form': form, 'email': new_email, 'can_resend': can_resend(last_otp)}
    return render(request, 'accounts/settings_email_otp.html', context)


@login_required
def resend_settings_email_otp(request):
    if request.method != 'POST':
        return redirect('accounts:settings_email')
    new_email = request.session.get(EMAIL_CHANGE_KEY)
    if not new_email:
        return redirect('accounts:settings_email')
    last_otp = (
        EmailOTP.objects.filter(email=new_email, farm=None, purpose=EmailOTP.Purpose.EMAIL_CHANGE)
        .order_by('-created_at')
        .first()
    )
    if can_resend(last_otp):
        if _try_issue_otp(request, new_email, EmailOTP.Purpose.EMAIL_CHANGE, farm=None):
            messages.success(request, _('A new code is on its way.'))
    else:
        messages.warning(request, _('Please wait a little before requesting another code.'))
    return redirect('accounts:settings_email_otp')
