import random
import re
import string

from django.conf import settings
from django.db import models
from django_countries.fields import CountryField


def _initials_from_name(name):
    letters = re.sub(r'[^A-Za-z]', '', name).upper()
    if len(letters) >= 2:
        return letters[:2]
    return (letters + 'XX')[:2]


def generate_farm_code(name):
    """8-char farm code: first two letters of the farm name + 6 random
    alphanumeric characters, e.g. 'GR7K9QAB' for 'Green Valley'."""
    prefix = _initials_from_name(name)
    alphabet = string.ascii_uppercase + string.digits
    while True:
        suffix = ''.join(random.choices(alphabet, k=6))
        code = f'{prefix}{suffix}'
        if not Farm.objects.filter(code=code).exists():
            return code


class Farm(models.Model):
    name = models.CharField(max_length=150)
    code = models.CharField(max_length=8, unique=True, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='owned_farms'
    )
    country = CountryField(default='KE', blank=True)
    county = models.CharField(max_length=100, blank=True)
    location = models.CharField(max_length=200, blank=True)
    is_active = models.BooleanField(default=True)
    setup_completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f'{self.name} ({self.code})'

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = generate_farm_code(self.name)
        super().save(*args, **kwargs)

    @property
    def block_count(self):
        return self.blocks.count()

    @property
    def cow_count(self):
        return self.cows.filter(status='active').count()


class Block(models.Model):
    """A paddock / shed block within a farm, e.g. 'Block A'."""

    farm = models.ForeignKey(Farm, on_delete=models.CASCADE, related_name='blocks')
    name = models.CharField(max_length=100)
    description = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='created_blocks'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('farm', 'name')
        ordering = ['name']

    def __str__(self):
        return f'{self.name} - {self.farm.name}'

    @property
    def active_cow_count(self):
        return self.cows.filter(status='active').count()


class FarmRole(models.TextChoices):
    FARMER = 'farmer', 'Farmer (Owner)'
    MANAGER = 'farm_manager', 'Farm Manager'
    SUPERVISOR = 'farm_supervisor', 'Farm Supervisor'
    WORKER = 'farm_worker', 'Farm Worker'


# Roles a given role is allowed to invite/assign to new members.
ASSIGNABLE_ROLES: dict[str, list[FarmRole]] = {
    FarmRole.FARMER: [FarmRole.MANAGER, FarmRole.SUPERVISOR, FarmRole.WORKER],
    FarmRole.MANAGER: [FarmRole.SUPERVISOR, FarmRole.WORKER],
}

ROLES_THAT_MANAGE_WORKERS = {FarmRole.FARMER, FarmRole.MANAGER}
ROLES_THAT_MANAGE_HERD = {FarmRole.FARMER, FarmRole.MANAGER, FarmRole.SUPERVISOR}
ROLES_THAT_RECORD_PRODUCTION = {
    FarmRole.FARMER, FarmRole.MANAGER, FarmRole.SUPERVISOR, FarmRole.WORKER
}


class FarmMembership(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        ACTIVE = 'active', 'Active'
        SUSPENDED = 'suspended', 'Suspended'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='farm_memberships'
    )
    farm = models.ForeignKey(Farm, on_delete=models.CASCADE, related_name='memberships')
    role = models.CharField(max_length=20, choices=FarmRole.choices)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='invited_members'
    )
    last_notifications_read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'farm')
        ordering = ['farm', 'role']

    def __str__(self):
        return f'{self.user} @ {self.farm} ({self.get_role_display()})'

    @property
    def can_add_farms(self):
        return self.role == FarmRole.FARMER

    @property
    def can_manage_workers(self):
        return self.role in ROLES_THAT_MANAGE_WORKERS

    @property
    def can_manage_herd(self):
        return self.role in ROLES_THAT_MANAGE_HERD

    @property
    def can_record_production(self):
        return self.role in ROLES_THAT_RECORD_PRODUCTION

    @property
    def can_edit_or_delete(self):
        return self.role in ROLES_THAT_MANAGE_HERD

    @property
    def can_view_all_notifications(self):
        # Farmer + Farm Manager see the whole farm's activity feed;
        # everyone else sees only their own actions.
        return self.role in ROLES_THAT_MANAGE_WORKERS

    @property
    def assignable_roles(self):
        return ASSIGNABLE_ROLES.get(self.role, [])
