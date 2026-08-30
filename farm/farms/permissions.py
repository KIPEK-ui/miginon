from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.utils.translation import gettext_lazy as _

from .models import FarmMembership, FarmRole


def get_active_membership(request):
    """Resolve the FarmMembership the request should act on: the farm
    selected via the switcher if still valid, else the user's first active
    membership."""
    if not request.user.is_authenticated:
        return None
    farm_id = request.session.get('active_farm_id')
    qs = FarmMembership.objects.filter(
        user=request.user, status=FarmMembership.Status.ACTIVE
    ).select_related('farm')
    membership = None
    if farm_id:
        membership = qs.filter(farm_id=farm_id).first()
    if not membership:
        membership = qs.first()
    if membership:
        request.session['active_farm_id'] = membership.farm_id
    return membership


def farm_permission_required(check, message=_("You don't have permission to do that.")):
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def _wrapped(request, *args, **kwargs):
            membership = get_active_membership(request)
            if not membership:
                messages.error(request, _('You need to belong to a farm to do that.'))
                return redirect('farms:dashboard')
            if not check(membership):
                messages.error(request, message)
                return redirect('farms:dashboard')
            request.membership = membership
            request.farm = membership.farm
            return view_func(request, *args, **kwargs)
        return _wrapped
    return decorator


manage_workers_required = farm_permission_required(
    lambda m: m.can_manage_workers, _("Only farmers and farm managers can manage workers.")
)
manage_herd_required = farm_permission_required(
    lambda m: m.can_manage_herd, _("You don't have permission to manage the herd.")
)
record_production_required = farm_permission_required(
    lambda m: m.can_record_production, _("You don't have permission to add records.")
)
any_member_required = farm_permission_required(lambda m: True)

# Generic aliases with the same underlying role checks as the herd/production
# rules above, used by other structural modules (crops, inventory, finance)
# so every module in the app enforces identical permission tiers:
#   - "manage" level (Farmer/Manager/Supervisor): add structural entities
#     (cows, crops, inventory items).
#   - "log" level (Farmer/Manager/Supervisor/Worker): record day-to-day
#     activity (milk, feeding, crop activity, stock movements, transactions).
manage_records_required = manage_herd_required
log_activity_required = record_production_required

# Analysis is available to the same tier that manages the herd (Farmer,
# Farm Manager, Farm Supervisor) - Farm Workers get data entry, not reports.
analysis_required = farm_permission_required(
    lambda m: m.can_manage_herd, _('Analysis is available to farmers, managers and supervisors.')
)

# Editing or deleting an existing record is restricted to Farmer, Farm
# Manager and Farm Supervisor - a Farm Worker can log new records but can't
# alter or remove what's already been recorded.
edit_delete_required = farm_permission_required(
    lambda m: m.can_edit_or_delete, _('Only farmers, managers and supervisors can edit or delete records.')
)


def farmer_required(view_func):
    @wraps(view_func)
    @login_required
    def _wrapped(request, *args, **kwargs):
        if not FarmMembership.objects.filter(
            user=request.user, role=FarmRole.FARMER, status=FarmMembership.Status.ACTIVE
        ).exists():
            messages.error(request, _('Only farm owners can add new farms.'))
            return redirect('farms:dashboard')
        return view_func(request, *args, **kwargs)
    return _wrapped


def platform_admin_required(view_func):
    @wraps(view_func)
    @login_required
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_platform_admin:
            messages.error(request, _('Platform admin access only.'))
            return redirect('farms:dashboard')
        return view_func(request, *args, **kwargs)
    return _wrapped
