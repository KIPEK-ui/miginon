from django.conf import settings
from django.db.models import Q, Sum
from django.utils.translation import gettext_lazy as _

from .models import FarmMembership

# The dashboard-grid "modules" the floating bottom nav can offer as recent
# shortcuts - keyed by the URL app_name Django's resolver reports, so
# tracking a visit is just "is this app_name one we care about" with no
# per-view special-casing. Icons/labels mirror the matching card on
# farms/dashboard.html for visual consistency. farms/accounts themselves are
# deliberately excluded - the dashboard IS the farms module, and settings/
# worker-management aren't "modules" in the daily-use sense this nav is for.
BOTTOM_NAV_MODULES = {
    'cows': {'icon': 'paw-outline', 'label': _('Cows'), 'url': 'cows:cow_list'},
    'crops': {'icon': 'leaf-outline', 'label': _('Crops'), 'url': 'crops:crop_list'},
    'finance': {'icon': 'cash-outline', 'label': _('Finance'), 'url': 'finance:transaction_list'},
    'inventory': {'icon': 'cube-outline', 'label': _('Inventory'), 'url': 'inventory:item_list'},
    'tasks': {'icon': 'checkbox-outline', 'label': _('Tasks'), 'url': 'tasks:task_list'},
    'analysis': {'icon': 'stats-chart-outline', 'label': _('Reports'), 'url': 'analysis:overview'},
    'weather': {'icon': 'partly-sunny-outline', 'label': _('Weather'), 'url': 'weather:forecast'},
    'advisory': {'icon': 'school-outline', 'label': _('Advisory'), 'url': 'advisory:home'},
    'blockchain': {'icon': 'wallet-outline', 'label': _('Wallet'), 'url': 'blockchain:wallet'},
    'creditscore': {'icon': 'speedometer-outline', 'label': _('Credit score'), 'url': 'creditscore:overview'},
}
RECENT_MODULES_SESSION_KEY = 'recent_module_history'
RECENT_MODULES_SHOWN = 4
RECENT_MODULES_HISTORY_LENGTH = 8


def active_farm(request):
    """Expose the signed-in user's farm memberships and the currently
    selected farm (for the farm switcher in the nav) to every template."""
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return {}

    memberships = list(
        FarmMembership.objects.filter(user=user, status=FarmMembership.Status.ACTIVE)
        .select_related('farm')
    )
    if not memberships:
        return {'my_memberships': [], 'active_membership': None, 'active_farm_obj': None}

    active_farm_id = request.session.get('active_farm_id')
    active_membership = next(
        (m for m in memberships if m.farm_id == active_farm_id), memberships[0]
    )
    request.session.setdefault('active_farm_id', active_membership.farm_id)

    from notifications.models import Notification

    notif_qs = Notification.objects.filter(farm=active_membership.farm)
    if not active_membership.can_view_all_notifications:
        notif_qs = notif_qs.filter(Q(actor=user) | Q(recipient=user))
    since = active_membership.last_notifications_read_at or active_membership.created_at
    unread_notifications_count = notif_qs.filter(created_at__gt=since).count()

    from blockchain.models import FiqLedgerEntry

    fiq_balance = FiqLedgerEntry.objects.filter(
        farm=active_membership.farm
    ).aggregate(total=Sum('amount'))['total'] or 0

    return {
        'my_memberships': memberships,
        'active_membership': active_membership,
        'active_farm_obj': active_membership.farm,
        'unread_notifications_count': unread_notifications_count,
        'vapid_public_key': getattr(settings, 'VAPID_PUBLIC_KEY', ''),
        'fiq_balance': fiq_balance,
        'recent_modules': _track_and_get_recent_modules(request),
    }


def _track_and_get_recent_modules(request):
    """Records the current page's module (if it's one of BOTTOM_NAV_MODULES)
    at the front of a session-held history, then returns up to the
    RECENT_MODULES_SHOWN most recently visited OTHER modules for the
    floating bottom nav - session-based and per-device, same persistence
    model already used for active_farm_id above, not something that needs
    a DB column."""
    resolver_match = getattr(request, 'resolver_match', None)
    current_app = resolver_match.app_name if resolver_match else None

    history = request.session.get(RECENT_MODULES_SESSION_KEY, [])
    if current_app in BOTTOM_NAV_MODULES:
        history = [current_app] + [app for app in history if app != current_app]
        history = history[:RECENT_MODULES_HISTORY_LENGTH]
        if history != request.session.get(RECENT_MODULES_SESSION_KEY):
            request.session[RECENT_MODULES_SESSION_KEY] = history

    recent = [app for app in history if app != current_app][:RECENT_MODULES_SHOWN]
    return [{'app': app, **BOTTOM_NAV_MODULES[app]} for app in recent]
