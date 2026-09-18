from django.core.management.base import BaseCommand

from core.demo import DEMO_FARM_NAME, get_or_create_demo_farm


class Command(BaseCommand):
    help = (
        "Optional: pre-creates the public /demo/ walkthrough's shared farm "
        "and sample data up front. Not required - core.views.demo_login "
        "creates the same thing automatically the first time anyone visits "
        "/demo/ (see core.demo.get_or_create_demo_farm) - running this just "
        "avoids paying that one-time seeding cost on whichever visitor "
        "happens to be first."
    )

    def handle(self, *args, **options):
        farm, _user = get_or_create_demo_farm()
        self.stdout.write(self.style.SUCCESS(f'"{DEMO_FARM_NAME}" is ready (farm id {farm.id}).'))
