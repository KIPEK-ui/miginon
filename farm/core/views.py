from django.conf import settings
from django.shortcuts import redirect, render
from django.utils.translation import gettext_lazy as _

from accounts.models import User

THEME_COOKIE_MAX_AGE = 60 * 60 * 24 * 365  # 1 year


def _redirect_back(request):
    return redirect(request.POST.get('next') or request.META.get('HTTP_REFERER') or 'core:landing')


def set_theme(request):
    """Toggle light/dark. Always set on the `theme` cookie (so it works for
    anonymous visitors too - see core.context_processors.theme), and mirror
    it onto the signed-in user's saved preference so it follows them across
    devices."""
    if request.method != 'POST':
        return _redirect_back(request)
    new_theme = 'dark' if request.COOKIES.get('theme', 'light') != 'dark' else 'light'
    if request.user.is_authenticated:
        new_theme = 'dark' if request.user.theme_preference != User.ThemePreference.DARK else 'light'
        request.user.theme_preference = new_theme
        request.user.save(update_fields=['theme_preference'])
    response = _redirect_back(request)
    response.set_cookie('theme', new_theme, max_age=THEME_COOKIE_MAX_AGE)
    return response


def set_language(request):
    """Same idea as Django's built-in django.views.i18n.set_language, kept as
    our own view so a signed-in user's choice is also saved on their account
    (LocaleMiddleware itself is cookie-only as of Django 4+ - there's no
    session-based language key to piggyback on, so the account field is what
    makes the choice follow a user across devices/browsers)."""
    if request.method != 'POST':
        return _redirect_back(request)
    lang = request.POST.get('language')
    valid_codes = {code for code, _ in settings.LANGUAGES}
    if lang not in valid_codes:
        return _redirect_back(request)
    response = _redirect_back(request)
    response.set_cookie(settings.LANGUAGE_COOKIE_NAME, lang, max_age=THEME_COOKIE_MAX_AGE)
    if request.user.is_authenticated:
        request.user.language = lang
        request.user.save(update_fields=['language'])
    return response


def landing(request):
    if request.user.is_authenticated:
        return redirect('farms:dashboard')

    features = [
        ('layers-outline', _('3D farm visualization'), _('Explore your whole farm in an interactive 3D view - paddocks, herd, crops, tasks, inventory and finance, all in one place.')),
        ('trending-up-outline', _('AI production predictions'), _('Get milk yield forecasts per cow, block or herd, with an honest, exact breakdown of what’s driving each prediction - not a black box.')),
        ('partly-sunny-outline', _('Weather & field advisory'), _('Live 5-day forecasts for your exact farm location, plus plain-language advisories - know when to hold off spraying or add extra water before a hot, dry spell.')),
        ('school-outline', _('Farming & dairy advisory'), _('A sourced disease catalog for dairy cattle and crops with symptoms, prevention and treatment, step-by-step guides for silage, milk value addition and planting, and the nearest KALRO center to your farm.')),
        ('water-outline', _('Milk production'), _('Log AM, noon and PM yields per cow and block, with the session set automatically from the time you record - production becomes trackable stock, and a sale updates your finances and inventory together.')),
        ('nutrition-outline', _('Feeding records'), _('Record dairy meal and silage/hay per block or per individual cow, with automatic stock draw-down and a suggested feed composition to get you started.')),
        ('paw-outline', _('Herd management'), _('Organize cows, heifers, calves and bulls into blocks with tags, breed, gender, calving dates and status - transfer between blocks in a click.')),
        ('leaf-outline', _('Crop tracking'), _('Track every crop from planting to harvest - a logged harvest automatically restocks your produce inventory.')),
        ('checkbox-outline', _('Task management'), _('Assign tasks to your team tied to a block, crop or piece of equipment, and track them through to done.')),
        ('cube-outline', _('Inventory & stock'), _('Track feed, veterinary supplies, equipment and produce, with automatic low-stock warnings and per-worker equipment usage.')),
        ('cash-outline', _('Finance'), _('Record income and expenses by category and see your real-time net position for the farm.')),
        ('bar-chart-outline', _('Reports & analytics'), _('A full dashboard plus one-click exports to CSV, Excel or PDF - or have a report emailed to you instantly, weather included.')),
        ('notifications-circle-outline', _('Device notifications'), _('Get notified on your phone or browser the moment something needs attention - a task, a completed job, low stock - even when the app is closed.')),
        ('notifications-outline', _('Activity feed'), _('Every teammate sees who added, changed or removed what, in real time, right on their dashboard.')),
        ('moon-outline', _('Light & dark mode'), _('Switch between a bright or dark theme any time - it’s saved to your account and remembered on every device.')),
        ('language-outline', _('English & Kiswahili'), _('Use FarmIQ in English or Kiswahili - switch any time from the header, and it’s remembered for next time.')),
        ('lock-closed-outline', _('Passwordless login'), _('No passwords to remember or leak. Sign in with your Farm ID, email and a 6-digit one-time code.')),
        ('people-outline', _('Role-based access'), _('Farmer, Manager, Supervisor and Worker - everyone sees exactly the tools their role needs, nothing more.')),
        ('business-outline', _('Multi-farm support'), _('Run more than one farm from a single account, each with its own team, herd and records.')),
        ('phone-portrait-outline', _('Install as an app'), _('Add FarmIQ to your home screen and use it full-screen, offline-friendly, like a native app.')),
    ]

    steps = [
        ('1', _('Create your farm'), _('Sign up in under a minute and get a unique Farm ID instantly - that ID is how your whole team signs in.')),
        ('2', _('Set up blocks & herd'), _('Add your blocks or paddocks, then register your cows, heifers, calves and bulls against them.')),
        ('3', _('Invite your team'), _('Add managers, supervisors and workers by email. No passwords to hand out - just OTP codes.')),
        ('4', _('Log daily & review'), _('Record milk, feeding, crops, inventory and finance as you go, then check the dashboard or export a report.')),
    ]

    return render(request, 'core/landing.html', {'features': features, 'steps': steps})
