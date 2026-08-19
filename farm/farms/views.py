from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from core.email import send_styled_email_safely
from cows.models import Cow, FeedingRecord, MilkRecord
from crops.models import Crop, CropActivity
from finance.models import Transaction
from inventory.models import InventoryItem, StockMovement
from notifications.models import Notification
from notifications.services import notify
from tasks.models import Task

from .forms import BlockForm, FarmForm, FarmSettingsForm, WorkerInviteForm, WorkerRoleForm
from .kenya_data import COUNTY_TOWNS
from .models import Block, Farm, FarmMembership, FarmRole
from .permissions import (
    any_member_required,
    edit_delete_required,
    farmer_required,
    get_active_membership,
    manage_herd_required,
    manage_workers_required,
    platform_admin_required,
)
from .services import send_worker_added_email

# --------------------------------------------------------------------- home
#
# Every "log a record" action on the dashboard is driven from this one list
# rather than a pile of copy-pasted {% if %} blocks in the template. Each
# entry's `permission` is checked against the viewer's FarmMembership, so
# adding a new loggable record type (or changing who may log it) is a
# one-line change here instead of a template edit - this is the same
# role-abstraction pattern as FarmMembership.can_record_production itself,
# just applied to "which buttons does this role see" rather than "can this
# request proceed".
QUICK_ACTIONS = [
    {
        'label': 'Log milk', 'url_name': 'cows:milk_create', 'icon': 'water-outline',
        'permission': lambda m: m.can_record_production,
    },
    {
        'label': 'Log feed', 'url_name': 'cows:feeding_create', 'icon': 'nutrition-outline',
        'permission': lambda m: m.can_record_production,
    },
    {
        'label': 'Log crop activity', 'url_name': 'crops:activity_create', 'icon': 'flower-outline',
        'permission': lambda m: m.can_record_production,
    },
    {
        'label': 'Record stock movement', 'url_name': 'inventory:movement_create', 'icon': 'swap-horizontal-outline',
        'permission': lambda m: m.can_record_production,
    },
    {
        'label': 'Log expense', 'url_name': 'finance:transaction_create', 'icon': 'cash-outline',
        'permission': lambda m: m.can_record_production,
    },
    {
        'label': 'Record milk sale', 'url_name': 'finance:milk_sale_create', 'icon': 'water-outline',
        'permission': lambda m: m.can_record_production,
    },
    {
        'label': 'Assign task', 'url_name': 'tasks:task_create', 'icon': 'checkbox-outline',
        'permission': lambda m: m.can_manage_workers,
    },
]


@login_required
def dashboard(request):
    if request.user.is_platform_admin:
        return platform_dashboard(request)

    membership = get_active_membership(request)
    if not membership:
        messages.info(request, 'You are not linked to a farm yet.')
        return render(request, 'farms/no_farm.html')

    farm = membership.farm
    today = timezone.now().date()
    month_start = today.replace(day=1)

    milk_today = MilkRecord.objects.filter(farm=farm, date=today).aggregate(total=Sum('liters'))['total'] or 0
    feed_today = FeedingRecord.objects.filter(farm=farm, date=today).count()
    blocks = Block.objects.filter(farm=farm).order_by('name')
    recent_milk = MilkRecord.objects.filter(farm=farm).select_related('cow', 'block')[:6]
    recent_feed = FeedingRecord.objects.filter(farm=farm).select_related('block')[:6]

    crop_count = Crop.objects.filter(farm=farm).count()
    recent_crop_activity = CropActivity.objects.filter(farm=farm).select_related('crop')[:6]

    low_stock_items = [item for item in InventoryItem.objects.filter(farm=farm) if item.is_low_stock]
    recent_stock_movements = StockMovement.objects.filter(farm=farm).select_related('item')[:6]

    month_totals = Transaction.objects.filter(farm=farm, date__gte=month_start).aggregate(
        income=Sum('amount', filter=Q(kind=Transaction.Kind.INCOME)),
        expense=Sum('amount', filter=Q(kind=Transaction.Kind.EXPENSE)),
    )
    month_income = month_totals['income'] or 0
    month_expense = month_totals['expense'] or 0
    recent_transactions = Transaction.objects.filter(farm=farm)[:6]

    quick_actions = [action for action in QUICK_ACTIONS if action['permission'](membership)]

    my_open_tasks = Task.objects.filter(
        farm=farm, assigned_to=membership
    ).exclude(status__in=[Task.Status.DONE, Task.Status.CANCELLED]).select_related('block', 'crop')[:6]

    context = {
        'membership': membership,
        'farm': farm,
        'quick_actions': quick_actions,
        'blocks': blocks,
        'block_count': blocks.count(),
        'cow_count': Cow.objects.filter(farm=farm, status=Cow.Status.ACTIVE).count(),
        'milk_today': milk_today,
        'feed_today': feed_today,
        'recent_milk': recent_milk,
        'recent_feed': recent_feed,
        'crop_count': crop_count,
        'recent_crop_activity': recent_crop_activity,
        'low_stock_items': low_stock_items,
        'recent_stock_movements': recent_stock_movements,
        'month_income': month_income,
        'month_expense': month_expense,
        'month_net': month_income - month_expense,
        'recent_transactions': recent_transactions,
        'worker_count': FarmMembership.objects.filter(
            farm=farm, status=FarmMembership.Status.ACTIVE
        ).exclude(role=FarmRole.FARMER).count(),
        'my_open_tasks': my_open_tasks,
    }
    return render(request, 'farms/dashboard.html', context)


@platform_admin_required
def platform_dashboard(request):
    farms = Farm.objects.select_related('owner').order_by('-created_at')
    users = User.objects.order_by('-date_joined')
    context = {
        'farms': farms,
        'farm_count': farms.count(),
        'users': users[:20],
        'user_count': users.count(),
        'active_farms': farms.filter(is_active=True).count(),
    }
    return render(request, 'farms/admin_dashboard.html', context)


@platform_admin_required
def admin_toggle_farm(request, farm_id):
    farm = get_object_or_404(Farm, id=farm_id)
    if request.method == 'POST':
        farm.is_active = not farm.is_active
        farm.save(update_fields=['is_active'])
        # A platform admin disabling/enabling a farm is exactly the kind of
        # thing its own team should be able to see happened, and why their
        # farm suddenly stopped/started working - so it goes in the farm's
        # own notification feed too, not just an admin-side log.
        notify(
            farm, request.user, Notification.Verb.UPDATED, 'farm',
            f'{farm.name} was {"reactivated" if farm.is_active else "disabled"} by platform admin'
        )
        messages.success(request, f'{farm.name} is now {"active" if farm.is_active else "disabled"}.')
    return redirect('farms:admin_dashboard')


@platform_admin_required
def admin_toggle_user(request, user_id):
    # Not farm-scoped on purpose: a platform user can belong to several
    # farms (or none), so there's no single farm feed this event belongs
    # in - Notification always requires exactly one farm. This action stays
    # visible via Django admin's own history instead.
    user = get_object_or_404(User, id=user_id)
    if request.method == 'POST' and user != request.user:
        user.is_active = not user.is_active
        user.save(update_fields=['is_active'])
        messages.success(request, f'{user.get_full_name()} is now {"active" if user.is_active else "disabled"}.')
    return redirect('farms:admin_dashboard')


@login_required
def switch_farm(request, farm_id):
    if request.method == 'POST':
        exists = FarmMembership.objects.filter(
            user=request.user, farm_id=farm_id, status=FarmMembership.Status.ACTIVE
        ).exists()
        if exists:
            request.session['active_farm_id'] = farm_id
        else:
            messages.error(request, "You don't have access to that farm.")
    return redirect('farms:dashboard')


# --------------------------------------------------------------- add a farm

@farmer_required
def add_farm(request):
    form = FarmForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        farm = Farm.objects.create(
            name=form.cleaned_data['farm_name'],
            owner=request.user,
            country=form.cleaned_data['country'],
            county=form.cleaned_data['county'],
            location=form.cleaned_data['location'],
        )
        FarmMembership.objects.create(user=request.user, farm=farm, role=FarmRole.FARMER)
        request.session['active_farm_id'] = farm.id
        notify(farm, request.user, Notification.Verb.CREATED, 'farm', farm.name)
        messages.success(request, f'{farm.name} was created. Your farm ID is {farm.code}.')
        return redirect('farms:setup_block')
    return render(request, 'farms/add_farm.html', {'form': form, 'county_towns': COUNTY_TOWNS})


# --------------------------------------------------------------- farm settings

@farmer_required
def farm_settings(request):
    membership = get_active_membership(request)
    if not membership:
        messages.error(request, 'You need to belong to a farm to do that.')
        return redirect('farms:dashboard')
    farm = membership.farm
    if not membership.can_add_farms:
        messages.error(request, 'Only the farm owner can edit farm details.')
        return redirect('accounts:settings')

    form = FarmSettingsForm(request.POST or None, instance=farm)
    if request.method == 'POST' and form.is_valid():
        form.save()
        notify(farm, request.user, Notification.Verb.UPDATED, 'farm', farm.name)
        messages.success(request, 'Farm details updated.')
        return redirect('accounts:settings')
    return render(request, 'farms/farm_settings.html', {'form': form, 'farm': farm, 'county_towns': COUNTY_TOWNS})


# ---------------------------------------------------------- signup onboarding

@login_required
def signup_complete(request):
    farm_id = request.session.get('new_farm_id')
    farm = get_object_or_404(Farm, id=farm_id, owner=request.user) if farm_id else None
    if not farm:
        return redirect('farms:dashboard')
    return render(request, 'farms/signup_complete.html', {'farm': farm})


@login_required
def setup_block(request):
    membership = get_active_membership(request)
    if not membership or not membership.can_manage_herd:
        return redirect('farms:dashboard')
    farm = membership.farm
    blocks = Block.objects.filter(farm=farm).order_by('-created_at')

    wants_to_finish = request.method == 'POST' and 'finish' in request.POST
    name_provided = request.POST.get('name', '').strip() if request.method == 'POST' else ''

    # "Continue to cows" just needs at least one block to already exist - if
    # they didn't type a new one, there's nothing to validate, they're just
    # moving on. A blank name only blocks progress when the field is
    # actually needed (no blocks yet, or they're using "+ Add block").
    if wants_to_finish and not name_provided and blocks.exists():
        return redirect('farms:setup_cow')

    form = BlockForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        block = form.save(commit=False)
        block.farm = farm
        block.created_by = request.user
        block.save()
        notify(farm, request.user, Notification.Verb.CREATED, 'block', block.name)
        messages.success(request, f'{block.name} added.')
        if wants_to_finish:
            return redirect('farms:setup_cow')
        return redirect('farms:setup_block')

    return render(request, 'farms/setup_block.html', {'form': form, 'farm': farm, 'blocks': blocks})


def _finish_farm_setup(request, farm):
    already_completed = farm.setup_completed
    farm.setup_completed = True
    farm.save(update_fields=['setup_completed'])
    request.session.pop('new_farm_id', None)
    if not already_completed:
        send_styled_email_safely(
            to=farm.owner.email,
            subject=f'🎉 {farm.name} setup complete!',
            template_name='emails/milestone.html',
            context={
                'farm': farm,
                'title': 'Farm setup complete!',
                'description': (
                    f"{farm.name} now has its blocks and cows recorded on Farm IQ. "
                    "You're ready to start logging milk and feeding records daily."
                ),
                'dashboard_url': request.build_absolute_uri(reverse('farms:dashboard')),
            },
        )
    messages.success(request, 'Setup complete! Your dashboard is ready.')
    return redirect('farms:dashboard')


@login_required
def setup_cow(request):
    membership = get_active_membership(request)
    if not membership or not membership.can_manage_herd:
        return redirect('farms:dashboard')
    farm = membership.farm
    blocks = Block.objects.filter(farm=farm).order_by('name')
    if not blocks.exists():
        messages.info(request, 'Add at least one block first.')
        return redirect('farms:setup_block')

    wants_to_finish = request.method == 'POST' and 'finish' in request.POST
    tag_provided = request.POST.get('tag_id', '').strip() if request.method == 'POST' else ''

    # Cows aren't a hard requirement to finish setup (unlike blocks) - if
    # they didn't type a new tag, there's nothing to add, so "Finish setup"
    # just finishes, whether or not any cows exist yet.
    if wants_to_finish and not tag_provided:
        return _finish_farm_setup(request, farm)

    from cows.forms import CowForm
    form = CowForm(request.POST or None, farm=farm)
    if request.method == 'POST' and form.is_valid():
        cow = form.save(commit=False)
        cow.farm = farm
        cow.added_by = request.user
        cow.save()
        notify(farm, request.user, Notification.Verb.CREATED, 'cow', str(cow))
        messages.success(request, f'{cow} added.')
        if wants_to_finish:
            return _finish_farm_setup(request, farm)
        return redirect('farms:setup_cow')

    cows = Cow.objects.filter(farm=farm).order_by('-created_at')[:10]
    return render(request, 'farms/setup_cow.html', {'form': form, 'farm': farm, 'cows': cows})


# ------------------------------------------------------------------ workers

@manage_workers_required
def worker_list(request):
    workers = FarmMembership.objects.filter(farm=request.farm).select_related('user').order_by('role', 'user__first_name')
    return render(request, 'farms/worker_list.html', {'workers': workers})


@manage_workers_required
def worker_invite(request):
    membership = request.membership
    form = WorkerInviteForm(request.POST or None, assignable_roles=membership.assignable_roles)
    if request.method == 'POST' and form.is_valid():
        email = form.cleaned_data['email']
        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                'first_name': form.cleaned_data['first_name'],
                'last_name': form.cleaned_data['last_name'],
            },
        )
        membership_qs = FarmMembership.objects.filter(user=user, farm=request.farm)
        if membership_qs.exists():
            messages.error(request, f'{email} is already part of this farm.')
        else:
            new_membership = FarmMembership.objects.create(
                user=user, farm=request.farm, role=form.cleaned_data['role'], invited_by=request.user,
            )
            send_worker_added_email(new_membership, request)
            notify(
                request.farm, request.user, Notification.Verb.CREATED, 'worker',
                f'{user.get_full_name() or email} ({new_membership.get_role_display()})'
            )
            messages.success(request, f'{user.get_full_name() or email} added as {new_membership.get_role_display()}.')
            return redirect('farms:worker_list')
    return render(request, 'farms/worker_invite.html', {'form': form})


@manage_workers_required
def worker_update_role(request, membership_id):
    target = get_object_or_404(FarmMembership, id=membership_id, farm=request.farm)
    if target.role == FarmRole.FARMER:
        messages.error(request, "The farm owner's role can't be changed.")
        return redirect('farms:worker_list')

    form = WorkerRoleForm(request.POST or None, assignable_roles=request.membership.assignable_roles, initial={'role': target.role})
    if request.method == 'POST' and form.is_valid():
        target.role = form.cleaned_data['role']
        target.save(update_fields=['role'])
        notify(
            request.farm, request.user, Notification.Verb.UPDATED, 'worker',
            f'{target.user} is now {target.get_role_display()}'
        )
        messages.success(request, f'{target.user} is now {target.get_role_display()}.')
        return redirect('farms:worker_list')
    return render(request, 'farms/worker_update_role.html', {'form': form, 'target': target})


@manage_workers_required
def worker_suspend(request, membership_id):
    target = get_object_or_404(FarmMembership, id=membership_id, farm=request.farm)
    if target.role == FarmRole.FARMER:
        messages.error(request, "The farm owner can't be removed.")
    elif request.method == 'POST':
        target.status = (
            FarmMembership.Status.SUSPENDED
            if target.status == FarmMembership.Status.ACTIVE
            else FarmMembership.Status.ACTIVE
        )
        target.save(update_fields=['status'])
        notify(
            request.farm, request.user, Notification.Verb.UPDATED, 'worker',
            f'{target.user} is now {target.get_status_display()}'
        )
        messages.success(request, f'{target.user} is now {target.get_status_display()}.')
    return redirect('farms:worker_list')


# ------------------------------------------------------------------- blocks

@any_member_required
def block_list(request):
    blocks = Block.objects.filter(farm=request.farm).order_by('name')
    return render(request, 'farms/block_list.html', {'blocks': blocks})


@any_member_required
def farm_map(request):
    farm = request.farm
    today = timezone.now().date()
    month_start = today.replace(day=1)

    blocks = Block.objects.filter(farm=farm).order_by('name')
    feed_today_by_block = {}
    for rec in FeedingRecord.objects.filter(farm=farm, date=today):
        feed_today_by_block[rec.block_id] = (
            feed_today_by_block.get(rec.block_id, 0)
            + float(rec.dairy_meal_kg) + float(rec.silage_hay_kg)
        )

    blocks_data = [
        {
            'id': b.id,
            'name': b.name,
            'cow_count': b.active_cow_count,
            'feed_today_kg': feed_today_by_block.get(b.id, 0),
            'url': reverse('farms:block_detail', args=[b.id]),
        }
        for b in blocks
    ]

    cows = Cow.objects.filter(
        farm=farm, status__in=[Cow.Status.ACTIVE, Cow.Status.DRY]
    ).order_by('tag_id')
    cows_data = [
        {
            'id': c.id,
            'tag_id': c.tag_id,
            'name': c.name,
            'category': c.category,
            'gender': c.gender,
            'status': c.status,
            'block_id': c.block_id,
            'url': reverse('cows:cow_detail', args=[c.id]),
        }
        for c in cows
    ]

    items = InventoryItem.objects.filter(farm=farm).order_by('name')
    inventory_data = [
        {
            'id': i.id,
            'name': i.name,
            'category': i.category,
            'current_stock': float(i.current_stock),
            'reorder_level': float(i.reorder_level),
            'unit': i.unit,
            'is_low_stock': i.is_low_stock,
            'url': reverse('inventory:item_detail', args=[i.id]),
        }
        for i in items
    ]

    month_totals = Transaction.objects.filter(farm=farm, date__gte=month_start).aggregate(
        income=Sum('amount', filter=Q(kind=Transaction.Kind.INCOME)),
        expense=Sum('amount', filter=Q(kind=Transaction.Kind.EXPENSE)),
    )
    finance_data = {
        'income': float(month_totals['income'] or 0),
        'expense': float(month_totals['expense'] or 0),
        'url': reverse('finance:transaction_list'),
    }

    crops = Crop.objects.filter(farm=farm).order_by('name')
    crops_data = [
        {
            'id': c.id,
            'name': c.name,
            'field_name': c.field_name,
            'status': c.status,
            'url': reverse('crops:crop_detail', args=[c.id]),
        }
        for c in crops
    ]

    workers = FarmMembership.objects.filter(
        farm=farm, status=FarmMembership.Status.ACTIVE
    ).select_related('user').order_by('role', 'user__first_name')
    workers_data = [
        {
            'id': m.id,
            'name': m.user.get_short_name() or m.user.first_name,
            'role': m.role,
            'role_display': m.get_role_display(),
            'url': reverse('farms:worker_list'),
        }
        for m in workers
    ]

    open_tasks = Task.objects.filter(farm=farm).exclude(
        status__in=[Task.Status.DONE, Task.Status.CANCELLED]
    ).select_related('assigned_to__user')
    tasks_data = [
        {
            'id': t.id,
            'title': t.title,
            'status': t.status,
            'priority': t.priority,
            'block_id': t.block_id,
            'crop_id': t.crop_id,
            'assigned_to_id': t.assigned_to_id,
            'assigned_name': t.assigned_to.user.get_short_name() if t.assigned_to else 'Unassigned',
            'url': reverse('tasks:task_detail', args=[t.id]),
        }
        for t in open_tasks
    ]

    return render(request, 'farms/farm_map.html', {
        'blocks': blocks,
        'blocks_data': blocks_data,
        'cows_data': cows_data,
        'inventory_data': inventory_data,
        'finance_data': finance_data,
        'crops_data': crops_data,
        'workers_data': workers_data,
        'tasks_data': tasks_data,
        'feeding_url': reverse('cows:feeding_list'),
    })


@manage_herd_required
def block_create(request):
    form = BlockForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        block = form.save(commit=False)
        block.farm = request.farm
        block.created_by = request.user
        block.save()
        notify(request.farm, request.user, Notification.Verb.CREATED, 'block', block.name)
        messages.success(request, f'{block.name} added.')
        return redirect('farms:block_list')
    return render(request, 'farms/block_form.html', {'form': form})


@any_member_required
def block_detail(request, block_id):
    block = get_object_or_404(Block, id=block_id, farm=request.farm)
    cows = block.cows.all().order_by('tag_id')
    # context key can't be "block" - Django's {% block %} tag reserves that
    # name in the template's own context (for {{ block.super }}).
    return render(request, 'farms/block_detail.html', {'block_obj': block, 'cows': cows})


@edit_delete_required
def block_edit(request, block_id):
    block = get_object_or_404(Block, id=block_id, farm=request.farm)
    form = BlockForm(request.POST or None, instance=block)
    if request.method == 'POST' and form.is_valid():
        form.save()
        notify(request.farm, request.user, Notification.Verb.UPDATED, 'block', block.name)
        messages.success(request, f'{block.name} updated.')
        return redirect('farms:block_detail', block_id=block.id)
    return render(request, 'farms/block_form.html', {'form': form, 'block_obj': block})


@edit_delete_required
def block_delete(request, block_id):
    block = get_object_or_404(Block, id=block_id, farm=request.farm)
    if request.method == 'POST':
        description = block.name
        block.delete()
        notify(request.farm, request.user, Notification.Verb.DELETED, 'block', description)
        messages.success(request, f'{description} was deleted.')
        return redirect('farms:block_list')
    return redirect('farms:block_detail', block_id=block.id)
