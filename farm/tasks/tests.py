import datetime
from unittest.mock import patch

from django.test import TestCase

from accounts.models import User
from farms.models import Block, Farm, FarmMembership, FarmRole

from .models import Task


class TasksTestCase(TestCase):
    def setUp(self):
        self.farmer = User.objects.create_user(email='farmer@example.com', first_name='Fay')
        self.worker = User.objects.create_user(email='worker@example.com', first_name='Wes')
        self.farm = Farm.objects.create(name='Task Farm', owner=self.farmer)
        self.farmer_membership = FarmMembership.objects.create(user=self.farmer, farm=self.farm, role=FarmRole.FARMER)
        self.worker_membership = FarmMembership.objects.create(user=self.worker, farm=self.farm, role=FarmRole.WORKER)
        self.block = Block.objects.create(farm=self.farm, name='Block A')

    def _login(self, user):
        self.client.force_login(user)
        session = self.client.session
        session['active_farm_id'] = self.farm.id
        session.save()


class RecurringTaskTests(TasksTestCase):
    @patch('tasks.views.mint_fiq', return_value=None)
    def test_completing_a_recurring_task_creates_the_next_occurrence(self, mock_mint):
        task = Task.objects.create(
            farm=self.farm, title='Deworm herd', assigned_to=self.worker_membership, block=self.block,
            due_date=datetime.date(2026, 1, 1), repeat_every_days=90, created_by=self.farmer,
        )
        self._login(self.farmer)
        self.client.post(f'/tasks/{task.id}/status/', {'status': Task.Status.DONE})

        self.assertEqual(Task.objects.filter(farm=self.farm).count(), 2)
        next_task = Task.objects.exclude(id=task.id).get()
        self.assertEqual(next_task.title, 'Deworm herd')
        self.assertEqual(next_task.status, Task.Status.PENDING)
        self.assertEqual(next_task.due_date, datetime.date(2026, 4, 1))
        self.assertEqual(next_task.assigned_to, self.worker_membership)
        self.assertEqual(next_task.block, self.block)
        self.assertEqual(next_task.repeat_every_days, 90)

    @patch('tasks.views.mint_fiq', return_value=None)
    def test_completing_a_non_recurring_task_creates_nothing_extra(self, mock_mint):
        task = Task.objects.create(
            farm=self.farm, title='One-off cleaning', assigned_to=self.worker_membership,
            due_date=datetime.date(2026, 1, 1), created_by=self.farmer,
        )
        self._login(self.farmer)
        self.client.post(f'/tasks/{task.id}/status/', {'status': Task.Status.DONE})
        self.assertEqual(Task.objects.filter(farm=self.farm).count(), 1)

    @patch('tasks.views.mint_fiq', return_value=None)
    def test_marking_in_progress_does_not_spawn_a_next_occurrence(self, mock_mint):
        task = Task.objects.create(
            farm=self.farm, title='Deworm herd', assigned_to=self.worker_membership,
            due_date=datetime.date(2026, 1, 1), repeat_every_days=90, created_by=self.farmer,
        )
        self._login(self.worker)
        self.client.post(f'/tasks/{task.id}/status/', {'status': Task.Status.IN_PROGRESS})
        self.assertEqual(Task.objects.filter(farm=self.farm).count(), 1)

    def test_next_occurrence_anchors_off_today_when_no_due_date(self):
        task = Task.objects.create(
            farm=self.farm, title='No due date', assigned_to=self.worker_membership,
            repeat_every_days=7, created_by=self.farmer,
        )
        from django.utils import timezone
        next_task = task.create_next_occurrence()
        self.assertEqual(next_task.due_date, timezone.now().date() + datetime.timedelta(days=7))


class TaskPermissionTests(TasksTestCase):
    def test_worker_cannot_create_a_task(self):
        self._login(self.worker)
        self.client.post('/tasks/add/', {
            'title': 'New task', 'description': '', 'assigned_to': self.worker_membership.id,
            'block': '', 'crop': '', 'priority': Task.Priority.NORMAL, 'due_date': '', 'repeat_every_days': '',
        })
        self.assertFalse(Task.objects.filter(farm=self.farm, title='New task').exists())

    def test_farmer_can_create_a_task(self):
        self._login(self.farmer)
        self.client.post('/tasks/add/', {
            'title': 'New task', 'description': '', 'assigned_to': self.worker_membership.id,
            'block': '', 'crop': '', 'priority': Task.Priority.NORMAL, 'due_date': '', 'repeat_every_days': '',
        })
        self.assertTrue(Task.objects.filter(farm=self.farm, title='New task').exists())

    def test_worker_cannot_view_a_task_assigned_to_someone_else(self):
        other_worker = User.objects.create_user(email='other@example.com', first_name='Ot')
        other_membership = FarmMembership.objects.create(user=other_worker, farm=self.farm, role=FarmRole.WORKER)
        task = Task.objects.create(farm=self.farm, title='Not yours', assigned_to=other_membership, created_by=self.farmer)
        self._login(self.worker)
        response = self.client.get(f'/tasks/{task.id}/')
        self.assertEqual(response.status_code, 404)

    def test_worker_can_view_their_own_task(self):
        task = Task.objects.create(farm=self.farm, title='Yours', assigned_to=self.worker_membership, created_by=self.farmer)
        self._login(self.worker)
        response = self.client.get(f'/tasks/{task.id}/')
        self.assertEqual(response.status_code, 200)
