"""Shared identity + seed data for the public, read-only /demo/ walkthrough
(core.views.demo_login) - a fixed, shared farm and account that lets a
landing-page visitor click through the real app (dashboard, herd, credit
score, wallet, ...) with zero signup, while core.middleware.DemoModeMiddleware
blocks that account from ever mutating anything.

get_or_create_demo_farm is idempotent and safe to call on every visit -
it only actually seeds data the first time the farm doesn't exist yet, so
this also doubles as the optional `seed_demo_farm` management command
(same "not required, just avoids doing it lazily" idea as blockchain's
hedera_setup command).
"""
from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

DEMO_USER_EMAIL = 'demo@farmiq.solutions'
DEMO_FARM_NAME = 'FarmIQ Demo Farm'


def is_demo_user(user):
    return user.is_authenticated and user.email == DEMO_USER_EMAIL


def get_or_create_demo_farm():
    from accounts.models import User
    from farms.models import Farm, FarmMembership, FarmRole

    user, _user_created = User.objects.get_or_create(
        email=DEMO_USER_EMAIL, defaults={'first_name': 'Demo', 'last_name': 'Farmer'}
    )
    farm, farm_created = Farm.objects.get_or_create(
        owner=user, name=DEMO_FARM_NAME, defaults={'county': 'Nakuru', 'setup_completed': True}
    )
    FarmMembership.objects.get_or_create(
        farm=farm, user=user, defaults={'role': FarmRole.FARMER, 'status': FarmMembership.Status.ACTIVE}
    )
    if farm_created:
        _seed_sample_data(farm, user)
    return farm, user


def _seed_sample_data(farm, user):
    """Enough real activity across every module that a visitor lands on a
    populated page everywhere, not an empty state - mirrors the field
    usage in creditscore.tests._seed_quality, the existing reference for
    what a minimal-but-valid record looks like in each of these models."""
    from blockchain.models import FiqLedgerEntry
    from cows.models import Cow, MilkRecord, Session
    from creditscore.services import recompute_farm_score
    from crops.models import Crop
    from farms.models import Block
    from finance.models import Transaction
    from tasks.models import Task

    today = timezone.now().date()
    block = Block.objects.create(farm=farm, name='Block A')

    cows = [
        Cow.objects.create(farm=farm, tag_id=f'DEMO-{i}', breed=breed, status=Cow.Status.ACTIVE, block=block)
        for i, breed in enumerate(['Friesian', 'Ayrshire', 'Jersey'], start=1)
    ]
    records = [
        MilkRecord(
            farm=farm, cow=cow, block=block, date=today - timedelta(days=13 - offset),
            session=Session.AM, liters=Decimal('11.5'),
        )
        for offset in range(14) for cow in cows
    ]
    MilkRecord.objects.bulk_create(records)

    Crop.objects.create(
        farm=farm, name='Napier Grass', field_name='North Field', status=Crop.Status.GROWING,
        planted_on=today - timedelta(days=60), expected_harvest=today + timedelta(days=30), added_by=user,
    )

    Transaction.objects.create(
        farm=farm, kind=Transaction.Kind.INCOME, category=Transaction.Category.SALES, date=today, amount=Decimal('45000')
    )
    Transaction.objects.create(
        farm=farm, kind=Transaction.Kind.EXPENSE, category=Transaction.Category.FEED, date=today, amount=Decimal('12000')
    )

    Task.objects.create(
        farm=farm, title='Vaccinate herd', status=Task.Status.DONE,
        due_date=today - timedelta(days=2), completed_at=timezone.now() - timedelta(days=2),
    )
    Task.objects.create(farm=farm, title='Top-dress Napier block', status=Task.Status.PENDING, due_date=today + timedelta(days=3))

    FiqLedgerEntry.objects.create(farm=farm, amount=Decimal('50'), reason=FiqLedgerEntry.Reason.COW_REGISTERED, cow=cows[0])
    FiqLedgerEntry.objects.create(farm=farm, amount=Decimal('20'), reason=FiqLedgerEntry.Reason.TASK_COMPLETED)

    # Best-effort, like every other Hedera call in this codebase - a demo
    # seed shouldn't fail just because HEDERA_OPERATOR_KEY isn't set in
    # this environment (see blockchain.services' fail-silent contract).
    recompute_farm_score(farm, user=user)
