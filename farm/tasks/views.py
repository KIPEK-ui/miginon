from django.contrib import messages
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render

from farms.permissions import any_member_required, manage_workers_required
from notifications.models import Notification
from notifications.services import notify

from .forms import TaskForm
from .models import Task


def _visible_tasks(request):
    qs = Task.objects.filter(farm=request.farm).select_related('assigned_to__user', 'block', 'crop')
    if not request.membership.can_manage_workers:
        qs = qs.filter(assigned_to=request.membership)
    return qs


def _can_view(request, task):
    return request.membership.can_manage_workers or task.assigned_to_id == request.membership.id


@any_member_required
def task_list(request):
    tasks = _visible_tasks(request).exclude(status=Task.Status.CANCELLED)
    status_groups = [
        (Task.Status.PENDING, 'Pending'),
        (Task.Status.IN_PROGRESS, 'In progress'),
        (Task.Status.DONE, 'Done'),
    ]
    return render(request, 'tasks/task_list.html', {'tasks': tasks, 'status_groups': status_groups})


@manage_workers_required
def task_create(request):
    form = TaskForm(request.POST or None, farm=request.farm)
    if request.method == 'POST' and form.is_valid():
        task = form.save(commit=False)
        task.farm = request.farm
        task.created_by = request.user
        task.save()
        notify(
            request.farm, request.user, Notification.Verb.CREATED, 'task', task.title,
            recipient=task.assigned_to.user if task.assigned_to.user_id != request.user.id else None,
        )
        messages.success(request, f'"{task.title}" assigned to {task.assigned_to.user.get_short_name()}.')
        return redirect('tasks:task_list')
    return render(request, 'tasks/task_form.html', {'form': form})


@any_member_required
def task_detail(request, task_id):
    task = get_object_or_404(Task, id=task_id, farm=request.farm)
    if not _can_view(request, task):
        raise Http404
    can_update_status = _can_view(request, task) and task.status not in (Task.Status.DONE, Task.Status.CANCELLED)
    return render(request, 'tasks/task_detail.html', {
        'task': task,
        'can_update_status': can_update_status,
        'status_choices': Task.Status.choices,
    })


@manage_workers_required
def task_edit(request, task_id):
    task = get_object_or_404(Task, id=task_id, farm=request.farm)
    form = TaskForm(request.POST or None, instance=task, farm=request.farm)
    if request.method == 'POST' and form.is_valid():
        form.save()
        notify(request.farm, request.user, Notification.Verb.UPDATED, 'task', task.title)
        messages.success(request, f'"{task.title}" updated.')
        return redirect('tasks:task_detail', task_id=task.id)
    return render(request, 'tasks/task_form.html', {'form': form, 'task': task})


@manage_workers_required
def task_delete(request, task_id):
    task = get_object_or_404(Task, id=task_id, farm=request.farm)
    if request.method == 'POST':
        title = task.title
        task.delete()
        notify(request.farm, request.user, Notification.Verb.DELETED, 'task', title)
        messages.success(request, f'"{title}" deleted.')
        return redirect('tasks:task_list')
    return redirect('tasks:task_detail', task_id=task.id)


@any_member_required
def task_status_update(request, task_id):
    task = get_object_or_404(Task, id=task_id, farm=request.farm)
    if not _can_view(request, task):
        raise Http404
    new_status = request.POST.get('status')
    if request.method == 'POST' and new_status in Task.Status.values:
        task.mark_status(new_status)
        notify_recipient = None
        if new_status == Task.Status.DONE and task.created_by_id and task.created_by_id != request.user.id:
            notify_recipient = task.created_by
        notify(
            request.farm, request.user, Notification.Verb.UPDATED, 'task',
            f'{task.title} - {task.get_status_display()}',
            recipient=notify_recipient,
        )
        messages.success(request, f'"{task.title}" marked {task.get_status_display().lower()}.')
    return redirect('tasks:task_detail', task_id=task.id)
