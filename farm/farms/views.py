from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.models import User
from cows.models import Cow, FeedingRecord, MilkRecord
from notifications.models import Notification
from notifications.services import notify

from .forms import BlockForm, FarmForm, FarmSettingsForm, WorkerInviteForm, WorkerRoleForm
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

    milk_today = MilkRecord.objects.filter(farm=farm, date=today).aggregate(total=Sum('liters'))['total'] or 0
    feed_today = FeedingRecord.objects.filter(farm=farm, date=today).count()
    blocks = Block.objects.filter(farm=farm).order_by('name')
    recent_milk = MilkRecord.objects.filter(farm=farm).select_related('cow', 'block')[:6]
    recent_feed = FeedingRecord.objects.filter(farm=farm).select_related('block')[:6]

    context = {
        'membership': membership,
        'farm': farm,
        'blocks': blocks,
        'block_count': blocks.count(),
        'cow_count': Cow.objects.filter(farm=farm, status=Cow.Status.ACTIVE).count(),
        'milk_today': milk_today,
        'feed_today': feed_today,
        'recent_milk': recent_milk,
        'recent_feed': recent_feed,
        'worker_count': FarmMembership.objects.filter(
            farm=farm, status=FarmMembership.Status.ACTIVE
        ).exclude(role=FarmRole.FARMER).count(),
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
        messages.success(request, f'{farm.name} is now {"active" if farm.is_active else "disabled"}.')
    return redirect('farms:admin_dashboard')


@platform_admin_required
def admin_toggle_user(request, user_id):
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
            location=form.cleaned_data['location'],
            county=form.cleaned_data['county'],
        )
        FarmMembership.objects.create(user=request.user, farm=farm, role=FarmRole.FARMER)
        request.session['active_farm_id'] = farm.id
        notify(farm, request.user, Notification.Verb.CREATED, 'farm', farm.name)
        messages.success(request, f'{farm.name} was created. Your farm ID is {farm.code}.')
        return redirect('farms:setup_block')
    return render(request, 'farms/add_farm.html', {'form': form})


# --------------------------------------------------------------- farm settings

@farmer_required
def farm_settings(request):
    membership = get_active_membership(request)
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
    return render(request, 'farms/farm_settings.html', {'form': form, 'farm': farm})


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
    form = BlockForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        block = form.save(commit=False)
        block.farm = farm
        block.created_by = request.user
        block.save()
        notify(farm, request.user, Notification.Verb.CREATED, 'block', block.name)
        messages.success(request, f'{block.name} added.')
        if 'finish' in request.POST:
            return redirect('farms:setup_cow')
        return redirect('farms:setup_block')

    blocks = Block.objects.filter(farm=farm).order_by('-created_at')
    return render(request, 'farms/setup_block.html', {'form': form, 'farm': farm, 'blocks': blocks})


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

    from cows.forms import CowForm
    form = CowForm(request.POST or None, farm=farm)
    if request.method == 'POST' and form.is_valid():
        cow = form.save(commit=False)
        cow.farm = farm
        cow.added_by = request.user
        cow.save()
        notify(farm, request.user, Notification.Verb.CREATED, 'cow', str(cow))
        messages.success(request, f'{cow} added.')
        if 'finish' in request.POST:
            farm.setup_completed = True
            farm.save(update_fields=['setup_completed'])
            request.session.pop('new_farm_id', None)
            messages.success(request, 'Setup complete! Your dashboard is ready.')
            return redirect('farms:dashboard')
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
            send_worker_added_email(new_membership)
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
