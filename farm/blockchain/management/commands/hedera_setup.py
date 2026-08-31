from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from blockchain.services import _CREATORS, _ensure_id, get_client


class Command(BaseCommand):
    help = (
        'Optional: pre-creates all 5 platform-shared Hedera token/topic '
        'types (herd registry, harvest certificates, FIQ, prediction and '
        'finance topics) up front. Not required - each is created '
        'automatically and saved to the database the first time it is '
        'actually needed (see blockchain.services._ensure_id) - running '
        'this just avoids paying that one-time creation cost on whichever '
        'real user action happens to be first.'
    )

    def handle(self, *args, **options):
        client = get_client()
        if client is None:
            raise CommandError('HEDERA_OPERATOR_ID / HEDERA_OPERATOR_KEY are not set in .env.')

        self.stdout.write(f'Ensuring Hedera tokens/topics exist on {settings.HEDERA_NETWORK}...')
        for field_name in _CREATORS:
            value = _ensure_id(client, field_name)
            self.stdout.write(self.style.SUCCESS(f'{field_name} = {value}'))

        self.stdout.write(self.style.SUCCESS('Done - IDs are saved in the database (blockchain.HederaConfig).'))
