import random
import string

from django.conf import settings
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('An email address is required.')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('platform_role', User.PlatformRole.ADMIN)
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        return self._create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """Email-first account. Farm-level roles (farmer / manager / supervisor /
    worker) live on FarmMembership, not here - a person can hold different
    roles on different farms. platform_role is only for the small group of
    people who run the platform itself (support/oversight), separate from
    is_superuser which grants full Django admin access."""

    class PlatformRole(models.TextChoices):
        NONE = '', 'Farm user'
        ADMIN = 'admin', 'Platform Admin'

    class NotificationDelivery(models.TextChoices):
        IN_APP = 'in_app', 'In-app only'
        PUSH = 'push', 'Device notifications only'
        BOTH = 'both', 'Both'

    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=60)
    last_name = models.CharField(max_length=60, blank=True)
    phone = models.CharField(max_length=20, blank=True)

    platform_role = models.CharField(
        max_length=10, choices=PlatformRole.choices, blank=True, default=''
    )
    notification_delivery = models.CharField(
        max_length=10, choices=NotificationDelivery.choices, default=NotificationDelivery.BOTH,
        help_text='How you want to be notified about things targeted at you specifically '
                   '(a task assigned to you, low stock, etc.) - not the general farm activity feed.'
    )

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)
    last_login_at = models.DateTimeField(null=True, blank=True)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name']

    class Meta:
        ordering = ['-date_joined']

    def __str__(self):
        return self.get_full_name() or self.email

    def get_full_name(self):
        return f'{self.first_name} {self.last_name}'.strip()

    def get_short_name(self):
        return self.first_name

    @property
    def is_platform_admin(self):
        return self.is_superuser or self.platform_role == self.PlatformRole.ADMIN

    @property
    def initials(self):
        parts = [p[0] for p in (self.first_name, self.last_name) if p]
        return ''.join(parts).upper() or self.email[0].upper()


def generate_otp_code():
    return ''.join(random.choices(string.digits, k=6))


class EmailOTP(models.Model):
    class Purpose(models.TextChoices):
        LOGIN = 'login', 'Login'
        SIGNUP = 'signup', 'Signup verification'
        EMAIL_CHANGE = 'email_change', 'Email change verification'

    email = models.EmailField()
    farm = models.ForeignKey(
        'farms.Farm', null=True, blank=True, on_delete=models.CASCADE, related_name='otp_codes'
    )
    purpose = models.CharField(max_length=15, choices=Purpose.choices)
    code = models.CharField(max_length=6, default=generate_otp_code)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)
    attempts = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['email', 'purpose', 'farm'])]

    def __str__(self):
        return f'{self.email} - {self.purpose} - {self.code}'

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timezone.timedelta(
                minutes=settings.OTP_VALIDITY_MINUTES
            )
        super().save(*args, **kwargs)

    def is_valid(self):
        return (
            not self.is_used
            and self.attempts < settings.OTP_MAX_ATTEMPTS
            and timezone.now() < self.expires_at
        )

    def register_failed_attempt(self):
        self.attempts += 1
        self.save(update_fields=['attempts'])
